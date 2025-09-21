#!/usr/bin/env python3
"""
VERSION4 BETA
{*} WARNING: Writing full responses into CSV can create very large files.

"""

import sys, os, re, requests, random, threading, time, itertools, csv, warnings
from urllib.parse import urlsplit, parse_qsl
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests import Request
from colorama import Fore, Style, init

init(autoreset=True)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# Allow very large CSV fields (best-effort)
try:
	csv.field_size_limit(sys.maxsize)
except OverflowError:
	csv.field_size_limit(10**7)

# ================================== CONFIG ==================================
REQUEST_TIMEOUT = 60
REQUEST_RETRIES = 1
MAX_WORKERS = 12
THROTTLE_SECONDS = 0.0
SUMMARY_FILENAME = "summary.csv"
RESPONSE_PREVIEW_LEN = 2000
SHOW_FULL_RESPONSE = True        # whether to print full response to console (capped by MAX_RESPONSE_PRINT)
MAX_RESPONSE_PRINT = 100_000     # cap console print; set 0 for unlimited

USE_PROXY = False
PROXY_ADDR = "http://127.0.0.1:8080"
RECORD_PREPARED_RAW = True

USER_AGENTS = [
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
	"Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/142.0",
	"Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Mobile Safari/537.36",
]

_thread_local = threading.local()

# ================================== HELPERS ==================================
def get_thread_session():
	s = getattr(_thread_local, "session", None)
	if s is None:
		s = requests.Session()
		_thread_local.session = s
	return s

def sanitize_filename(s):
	return re.sub(r'[^\w\-_.]', '_', s) or "resp"

def safe_write_file(path, content):
	os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
	mode = "wb" if isinstance(content, (bytes, bytearray)) else "w"
	if mode == "w":
		with open(path, mode, encoding="utf-8", errors="ignore") as fh:
			fh.write(str(content))
	else:
		with open(path, mode) as fh:
			fh.write(content)

def format_duration(seconds: float) -> str:
	m, s = divmod(seconds, 60)
	h, m = divmod(m, 60)
	ms = int((s - int(s)) * 1000)
	return f"{int(h)}:{int(m):02d}:{int(s):02d}.{ms:03d}"

def build_raw_bytes_from_prepared(prep):
	start_line = f"{prep.method} {prep.path_url} HTTP/1.1\r\n"
	header_lines = "".join(f"{k}: {v}\r\n" for k, v in prep.headers.items())
	head = (start_line + header_lines + "\r\n").encode("utf-8")
	if prep.body is None:
		return head
	if isinstance(prep.body, bytes):
		return head + prep.body
	else:
		return head + str(prep.body).encode("utf-8")

# ================================== PARSING & DETECTION ==================================
def prompt_for_raw_request():
	print(Fore.CYAN + "\n"*2 + "[*] Paste raw HTTP request. Use ^^...^^ wrapper for placeholders.\n[*] End with 'END' or '..'\n" + Style.RESET_ALL)
	lines = []
	while True:
		try:
			l = input()
			if l.strip() == "END" or l.strip() == "..":
				break
			lines.append(l)
		except EOFError:
			break
	return "\n".join(lines)

def parse_request(raw_request: str):
	lines = raw_request.strip().splitlines()
	if not lines:
		raise ValueError("Empty request.")
	first = lines[0].strip()
	parts = first.split(" ", 2)
	if len(parts) < 2:
		raise ValueError("Malformed request line.")
	method = parts[0].upper()
	path = parts[1]
	headers = {}
	body_lines = []
	in_body = False
	for ln in lines[1:]:
		if not in_body and ln.strip() == "":
			in_body = True
			continue
		if not in_body:
			if ":" in ln:
				k, v = ln.split(":", 1)
				headers[k.strip()] = v.strip()
		else:
			body_lines.append(ln.rstrip("\r\n"))
	body = "\n".join(body_lines).strip()
	return method, path, headers, body

def detect_parameters_and_placeholders(path: str, body: str, headers: dict):
	params = {}
	try:
		parsed = urlsplit(path)
		for k, v in parse_qsl(parsed.query, keep_blank_values=True):
			if k not in params:
				params[k] = v
	except Exception:
		pass
	ct = headers.get("Content-Type", "")
	if ct and "application/x-www-form-urlencoded" in ct.lower():
		try:
			for k, v in parse_qsl(body, keep_blank_values=True):
				if k not in params:
					params[k] = v
		except Exception:
			pass
	else:
		for k, v in re.findall(r'([^\s&=]+)=([^&\r\n]*)', body):
			if k not in params:
				params[k] = v
	if not params:
		ref = headers.get("Referer") or headers.get("Origin") or ""
		try:
			parsed_ref = urlsplit(ref)
			for k, v in parse_qsl(parsed_ref.query, keep_blank_values=True):
				if k not in params:
					params[k] = v
		except Exception:
			pass
	combined = path + "\n" + body + "\n" + "\n".join(f"{k}:{v}" for k, v in headers.items())
	pat = re.compile(r'\^\^(.*?)\^\^', re.DOTALL)
	original_placeholders = [m.group(1) for m in pat.finditer(combined)]
	# use simple placeholder names PH1, PH2, ... (no spaces)
	placeholder_names = [f"PH{i+1}" for i in range(len(original_placeholders))]
	return params, placeholder_names, original_placeholders

# ================================== USER INPUT ==================================
def get_parameter_values(param_keys, placeholder_names, detected_params=None, detected_placeholders=None):
	values = {}

	# Handle normal detected parameters
	for k in param_keys:
		while True:
			# show detected default hint if available
			default_hint = f" (Detected: {detected_params[k]})" if (detected_params and k in detected_params) else ""
			choice = input(f"\n> Enter values for Detected Parameter '{k}':\n\t[f] load from file\n\t[m] manual single value\n\t[d] use detected/default value{default_hint}\n> Choose [ f / m / d ] (Default 'd', if detected else 'm'): ").strip().lower()
			if not choice:
				choice = "d" if (detected_params and k in detected_params) else "m"

			if choice == "f":
				p = input(f"> Enter file path for '{k}': ").strip()
				if os.path.isfile(p):
					with open(p, "r", encoding="utf-8", errors="ignore") as fh:
						vals = [ln.strip() for ln in fh if ln.strip()]
					if vals:
						values[k] = vals
						break
					else:
						print(Fore.RED + "[*] File empty.")
				else:
					print(Fore.RED + "[*] File not found.")

			elif choice == "m":
				v = input(f"> Enter single value for '{k}': ")
				values[k] = [v]
				break

			elif choice == "d":
				if detected_params and k in detected_params:
					values[k] = [detected_params[k]]
					print(Fore.CYAN + f"[*] Using detected/default value for '{k}': {detected_params[k]}" + Style.RESET_ALL)
					break
				else:
					print(Fore.YELLOW + "[*] No detected/default value available for this parameter; Choose another option." + Style.RESET_ALL)

			else:
				print("=> Invalid option.")

	# Handle placeholders
	for ph in placeholder_names:
		while True:
			ph_default = None
			if detected_placeholders and isinstance(detected_placeholders, dict):
				ph_default = detected_placeholders.get(ph)
			default_hint = f" (Detected: {ph_default})" if ph_default else ""
			choice = input(f"\n> Enter values for placeholder '{ph}':\n\t[f] load from file\n\t[m] manual single value\n\t[d] use detected/default value{default_hint}\n> Choose [ f / m / d ] (Default 'd', if detected else 'm'): ").strip().lower()
			if not choice:
				choice = "d" if ph_default else "m"

			if choice == "f":
				p = input(f"> Enter file path for '{ph}': ").strip()
				if os.path.isfile(p):
					with open(p, "r", encoding="utf-8", errors="ignore") as fh:
						vals = [ln.strip() for ln in fh if ln.strip()]
					if vals:
						values[ph] = vals
						break
					else:
						print(Fore.RED + "[*] File empty.")
				else:
					print(Fore.RED + "[*] File not found.")	
			elif choice == "m":
				v = input(f"> Enter single value for '{ph}': ")
				values[ph] = [v]
				break
			elif choice == "d":
				if ph_default is not None:
					values[ph] = [ph_default]
					print(Fore.CYAN + f"[*] Using detected/default value for '{ph}': {ph_default}" + Style.RESET_ALL)
					break
				else:
					print(Fore.YELLOW + "[*] No detected/default value available for this placeholder; choose another option." + Style.RESET_ALL)
			else:
				print("=> Invalid option.")
	return values

# ================================== COMBOS ==================================
def generate_combos_from_values(values_dict, attack_mode):
	ordered_keys = list(values_dict.keys())
	target_lists = [values_dict[k] for k in ordered_keys]

	# each parameter must have at least one value
	if any(len(lst) == 0 for lst in target_lists):
		raise ValueError("[*] Each parameter must have at least one value.")

	if attack_mode == "Sniper":
		combos = []
		for i, lst in enumerate(target_lists):
			for v in lst:
				combo = [target_lists[j][0] if j != i else v for j in range(len(target_lists))]
				combos.append(tuple(combo))

	elif attack_mode == "Pitchfork":
		if not all(len(lst) == len(target_lists[0]) for lst in target_lists):
			raise ValueError("[*] All lists must have same length for Pitchfork.")
		combos = list(zip(*target_lists))

	elif attack_mode == "Battering-ram":
		if not all(len(lst) == len(target_lists[0]) for lst in target_lists):
			raise ValueError("[*]All lists must have same length for Battering-ram.")
		combos = [tuple([target_lists[0][i]] * len(target_lists)) for i in range(len(target_lists[0]))]

	else:  # Clusterbomb / Cartesian product
		combos = list(itertools.product(*target_lists))

	return combos, ordered_keys

# ================================== REPLACEMENT & SENDING ==================================
def replace_wrapped_placeholders_in_text(text: str, placeholder_names, mapping, original_placeholders):
	# Use index-based mapping: PH1 -> original_placeholders[0], etc.
	for i, ph_name in enumerate(placeholder_names):
		if i < len(original_placeholders):
			orig = original_placeholders[i]
			val = mapping.get(ph_name, "")
			text = text.replace(f"^^{orig}^^", val)
	return text

def determine_scheme(path, headers):
	if re.match(r'^https?://', path):
		return urlsplit(path).scheme
	origin = (headers.get("Origin") or headers.get("Referer") or "").lower()
	if origin.startswith("https://"):
		return "https"
	host = headers.get("Host", "")
	if ":" in host:
		try:
			_, port = host.rsplit(":", 1)
			if port == "443":
				return "https"
		except Exception:
			pass
	return "http"

def build_sent_request_text(method, url, full_headers_dict, body):
	try:
		up = urlsplit(url)
		request_line = f"{method} {up.path or '/'}{('?' + up.query) if up.query else ''} HTTP/1.1"
	except Exception:
		request_line = f"{method} {url} HTTP/1.1"
	header_lines = []
	for k, v in full_headers_dict.items():
		header_lines.append(f"{k}: {v}")
	headers_text = "\n".join(header_lines) if header_lines else "(no headers)"
	body_text = body if body else "(empty)"
	return f"{request_line}\n{headers_text}\n\n{body_text}"

def _prepare_and_send(prep, session, proxies):
	last_exc = None
	for _ in range(REQUEST_RETRIES + 1):
		try:
			resp = session.send(prep, timeout=REQUEST_TIMEOUT, proxies=proxies, verify=False)
			return resp, None
		except requests.RequestException as e:
			last_exc = e
			continue
	return None, last_exc

def _send_single_request(idx, combo, method, path, headers, body, ordered_keys, outdir, session_headers, original_placeholders):
	try:
		start_req = time.time()
		time.sleep(random.uniform(0.02, 0.12))
		headers_copy = dict(headers)
		headers_copy["User-Agent"] = random.choice(USER_AGENTS)
		mapping = dict(zip(ordered_keys, combo))
		new_path = path
		new_body = body
		new_headers = dict(headers_copy)

		# Replace named parameters (name=val) for non-placeholder keys
		for name in ordered_keys:
			# placeholders start with PH, skip for this loop
			if name.startswith("PH"):
				continue
			val = mapping.get(name, "")
			if val is None:
				val = ""
			patt = re.compile(re.escape(f"{name}=") + r'[^&\s]*')
			new_path = patt.sub(f"{name}={val}", new_path)
			new_body = patt.sub(f"{name}={val}", new_body)
			for hk, hv in list(new_headers.items()):
				new_headers[hk] = patt.sub(f"{name}={val}", hv)

		# Now handle wrapped placeholders (^^...^^) using placeholder_names mapped to original_placeholders
		ph_names = [k for k in ordered_keys if k.startswith("PH")]
		if ph_names:
			new_path = replace_wrapped_placeholders_in_text(new_path, ph_names, mapping, original_placeholders)
			new_body = replace_wrapped_placeholders_in_text(new_body, ph_names, mapping, original_placeholders)
			for hk, hv in list(new_headers.items()):
				new_headers[hk] = replace_wrapped_placeholders_in_text(hv, ph_names, mapping, original_placeholders)

		scheme = determine_scheme(new_path, new_headers)
		if re.match(r'^https?://', new_path):
			url = new_path
		else:
			host = new_headers.get("Host")
			if not host:
				return {"idx": idx, "combo_frag": "_".join(f"{k}-{mapping.get(k,'')}" for k in ordered_keys), "status": None, "length": 0, "fname": "", "error": "No Host header", "time": 0.0, "request_text": "", "response_preview": "", "full_response": "", "raw_path": ""}
			if not new_path.startswith("/"):
				new_path = "/" + new_path
			url = f"{scheme}://{host}{new_path}"

		prepared_headers = {k: v for k, v in new_headers.items()}
		session = get_thread_session()
		req = Request(method, url, headers=prepared_headers, data=new_body if new_body else None)
		prep = session.prepare_request(req)

		raw_path = ""
		if RECORD_PREPARED_RAW:
			try:
				raw_bytes = build_raw_bytes_from_prepared(prep)
				raw_path = os.path.join(outdir, f"sent_raw_{idx:04d}.bin")
				os.makedirs(os.path.dirname(raw_path) or ".", exist_ok=True)
				with open(raw_path, "wb") as fh:
					fh.write(raw_bytes)
			except Exception:
				raw_path = ""

		proxies = {"http": PROXY_ADDR, "https": PROXY_ADDR} if USE_PROXY else None
		sent_request_text = build_sent_request_text(method, url, prepared_headers, new_body)
		resp, last_exc = _prepare_and_send(prep, session, proxies)
		elapsed_req = time.time() - start_req

		safe_frag = sanitize_filename("_".join(f"{k}-{mapping.get(k,'')}" for k in ordered_keys))[:150]
		resp_fname = f"response_{idx:04d}_{safe_frag}.txt"
		resp_path = os.path.join(outdir, resp_fname)

		if resp is None:
			return {"idx": idx, "combo_frag": "_".join(f"{k}-{mapping.get(k,'')}" for k in ordered_keys), "status": None, "length": 0, "fname": resp_fname, "error": f"Failed after retries: {last_exc}", "time": elapsed_req, "request_text": sent_request_text, "response_preview": "", "full_response": "", "raw_path": raw_path}

		# Save the full response safely using bytes -> decode (avoid truncation)
		try:
			content_bytes = resp.content
			try:
				resp_text = content_bytes.decode('utf-8')
			except Exception:
				resp_text = content_bytes.decode('utf-8', errors='replace')
			safe_write_file(resp_path, resp_text)
			length = len(resp_text)
		except Exception:
			# fallback to resp.text or empty
			try:
				resp_text = resp.text
				safe_write_file(resp_path, resp_text)
				length = len(resp_text)
			except Exception:
				resp_text = ""
				length = 0

		status = resp.status_code

		# build preview for console/CSV short column (but we also return full_response)
		if resp_text:
			if SHOW_FULL_RESPONSE:
				if MAX_RESPONSE_PRINT and len(resp_text) > MAX_RESPONSE_PRINT:
					preview = resp_text[:MAX_RESPONSE_PRINT] + "\n\n[TRUNCATED in console]\n"
				else:
					preview = resp_text
			else:
				preview = resp_text[:RESPONSE_PREVIEW_LEN]
		else:
			preview = ""

		return {
			"idx": idx,
			"combo_frag": "_".join(f"{k}-{mapping.get(k,'')}" for k in ordered_keys),
			"status": status,
			"length": length,
			"fname": resp_fname,
			"error": None,
			"time": elapsed_req,
			"request_text": sent_request_text,
			"response_preview": preview,
			"full_response": resp_text,
			"raw_path": raw_path,
		}
	except Exception as exc:
		return {"idx": idx, "combo_frag": "(error)", "status": None, "length": 0, "fname": "", "error": str(exc), "time": 0.0, "request_text": "", "response_preview": "", "full_response": "", "raw_path": ""}

# ================================== ORDERED CONCURRENT SENDER ==================================
def send_requests_concurrent(method, path, headers, body, combos, ordered_keys, outdir, session_headers, original_placeholders, max_workers=MAX_WORKERS, start_time=None):
	if start_time is None:
		start_time = time.time()
	print(Fore.CYAN + f"\n[*] [Attack started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}]" + Style.RESET_ALL)

	os.makedirs(outdir, exist_ok=True)
	summary_path = os.path.join(outdir, SUMMARY_FILENAME)
	with open(summary_path, "w", encoding="utf-8", newline="") as slog:
		writer = csv.writer(slog)
		writer.writerow(["index","params","status","length","filename","error","req_time_s","request","full_response","sent_raw_file"])

	total = len(combos)
	ex = ThreadPoolExecutor(max_workers=max_workers)
	future_map = {}
	results = {}
	lock = threading.Lock()
	summary_lines = []

	# submit tasks
	try:
		for idx, combo in enumerate(combos):
			fut = ex.submit(_send_single_request, idx+1, combo, method, path, headers, body, ordered_keys, outdir, session_headers, original_placeholders)
			future_map[fut] = idx+1
	except Exception as e:
		print(Fore.RED + f"Error submitting tasks: {e}" + Style.RESET_ALL)
		ex.shutdown(wait=False)
		return

	# collector: store results as they complete
	try:
		for fut in as_completed(future_map):
			try:
				res = fut.result()
			except Exception as e:
				idx = future_map.get(fut, None) or -1
				res = {"idx": idx, "combo_frag": "(unknown)", "status": None, "length": 0, "fname": "", "error": f"Worker exception: {e}", "time": 0.0, "request_text": "", "response_preview": "", "full_response": "", "raw_path": ""}
			with lock:
				results[res["idx"]] = res
	except KeyboardInterrupt:
		print(Fore.YELLOW + "\nKeyboardInterrupt detected — cancelling pending tasks..." + Style.RESET_ALL)
		try:
			ex.shutdown(wait=False, cancel_futures=True)
		except TypeError:
			ex.shutdown(wait=False)
	except Exception as e:
		print(Fore.RED + f"\nCollector error: {e}" + Style.RESET_ALL)
		try:
			ex.shutdown(wait=False)
		except Exception:
			pass

	# ordered printer
	try:
		for i in range(1, total+1):
			# wait until result i is available or all futures done
			while True:
				with lock:
					if i in results:
						res = results.pop(i)
						break
				time.sleep(0.02)
				if all(f.done() for f in future_map) and i not in results:
					res = {"idx": i, "combo_frag": "(missing)", "status": None, "length": 0, "fname": "", "error": "missing result (task failed or cancelled)", "time": 0.0, "request_text": "", "response_preview": "", "full_response": "", "raw_path": ""}
					break

			idx = res["idx"]
			combo_frag = res.get("combo_frag", "")
			status = res.get("status")
			length = res.get("length", 0)
			fname = res.get("fname", "")
			error = res.get("error")
			req_time = res.get("time", 0.0)
			request_text = res.get("request_text", "")
			response_preview = res.get("response_preview", "")
			full_response = res.get("full_response", "")
			raw_path = res.get("raw_path", "")

			combo_display = combo_frag.replace("_", " | ") if combo_frag else "(no params)"
			summary_lines.append((idx, total, combo_display, status, length, req_time, error))

			print(Fore.CYAN + f"\n[{idx}/{total}] Request -> " + Style.RESET_ALL + (combo_display if combo_display else "(no params)"))
			if request_text:
				for ln in request_text.splitlines():
					print(Fore.BLUE + "	 >> " + ln + Style.RESET_ALL)

			if error:
				print(Fore.RED + f"	 [-] Failed: {error}" + Style.RESET_ALL)
			else:
				if status is not None:
					if 200 <= status < 300:
						color, marker = Fore.GREEN, "[*]"
					elif 300 <= status < 400:
						color, marker = Fore.YELLOW, "[-]"
					else:
						color, marker = Fore.RED, "[-]"
					print(color + f"	 {marker} Status: {status} | Length: {length} chars | Time: {req_time:.3f}s" + Style.RESET_ALL)
				else:
					print(Fore.RED + "	 [-] No status returned." + Style.RESET_ALL)

			if full_response:
				if SHOW_FULL_RESPONSE:
					print(Fore.YELLOW + "	 >> Response body:" + Style.RESET_ALL)
					count = 0
					for ln in full_response.splitlines():
						if MAX_RESPONSE_PRINT and count >= MAX_RESPONSE_PRINT:
							print(Fore.YELLOW + "	  [Console output truncated]" + Style.RESET_ALL)
							break
						print(Fore.YELLOW + "	  " + ln + Style.RESET_ALL)
						count += len(ln) + 1
					if MAX_RESPONSE_PRINT and len(full_response) > MAX_RESPONSE_PRINT:
						print(Fore.YELLOW + f"	  [Response truncated in console at {MAX_RESPONSE_PRINT} chars; full response saved to {fname}]" + Style.RESET_ALL)
				else:
					first_line = response_preview.splitlines()[0] if response_preview.splitlines() else ""
					print(Fore.YELLOW + f"	 >> Response preview: {first_line[:200]}..." + Style.RESET_ALL)
			else:
				if fname:
					print(Fore.YELLOW + f"	 >> Full response saved to: {fname}" + Style.RESET_ALL)

			with open(summary_path, "a", encoding="utf-8", newline="") as slog:
				writer = csv.writer(slog)
				writer.writerow([idx, combo_frag, status if status is not None else "ERROR", length, fname, error or "", f"{req_time:.3f}", request_text, full_response, raw_path])

			if THROTTLE_SECONDS > 0:
				time.sleep(THROTTLE_SECONDS)

	finally:
		try:
			ex.shutdown(wait=False)
		except Exception:
			pass

	print(Fore.CYAN + "\n" + "-"*55 + " Attack Summary " + "-"*55 + "\n" + Style.RESET_ALL)
	for idx, total, combo_display, status, length, req_time, error in summary_lines:
		if error:
			line = f"[{idx}/{total}] Request -> {combo_display} \t [-] Failed: {error}"
			print(Fore.RED + line + Style.RESET_ALL)
		else:
			if status is None:
				line = f"[{idx}/{total}] Request -> {combo_display} \t [-] Status: None | Length: {length} chars | Time: {req_time:.3f}s"
				print(Fore.RED + line + Style.RESET_ALL)
			else:
				line = f"[{idx}/{total}] Request -> {combo_display} \t [*] Status: {status} | Length: {length} chars | Time: {req_time:.3f}s"
				if 200 <= status < 300:
					print(Fore.GREEN + line + Style.RESET_ALL)
				elif 300 <= status < 400:
					print(Fore.YELLOW + line + Style.RESET_ALL)
				else:
					print(Fore.RED + line + Style.RESET_ALL)

	elapsed = time.time() - start_time
	print(Fore.CYAN + f"\n[*] Total attack time: {elapsed:.2f} s ({format_duration(elapsed)})" + Style.RESET_ALL)

# ================================== MAIN ==================================
# ================================== MAIN ==================================
def main():
	start_all = time.time()
	try:
		raw = prompt_for_raw_request()
		method, path, headers, body = parse_request(raw)
		params, placeholder_names, original_placeholders = detect_parameters_and_placeholders(path, body, headers)

		print(Fore.YELLOW + "\n[*] Auto Detected Parameters:" + Style.RESET_ALL)
		if params:
			for i, (k, v) in enumerate(params.items(), start=1):
				print(f"{i}. {k} = {v}")
		else:
			print("\nNone Detected.")

		if placeholder_names:
			print(Fore.YELLOW + "\n[*] Detected Placeholders {PH} Parameter:\n" + Style.RESET_ALL)
			for i, ph in enumerate(placeholder_names, start=1):
				orig = original_placeholders[i-1] if i-1 < len(original_placeholders) else ""
				print(f"|> {ph} -> ^^{orig}^^")
		else:
			print("\nNo Placeholders Detected.")

		detected_placeholders = {ph: (original_placeholders[i-1] if i-1 < len(original_placeholders) else "") for i, ph in enumerate(placeholder_names, start=1)}

		ordered = list(params.keys()) + placeholder_names
		if not ordered:
			print(Fore.YELLOW + "No parameters or placeholders to set. Exiting." + Style.RESET_ALL)
			return

		values_dict = get_parameter_values(list(params.keys()), placeholder_names, detected_params=params, detected_placeholders=detected_placeholders)
		for k in ordered:
			if k not in values_dict:
				if k in params:
					values_dict[k] = [params[k]]
				else:
					values_dict[k] = [""]

		if any(len(vs) == 0 for vs in values_dict.values()):
			print(Fore.RED + "One or more parameters/placeholders have no values. Aborting." + Style.RESET_ALL)
			return

		multiple = any(len(vs) > 1 for vs in values_dict.values())
		session_headers = ["User-Agent","Accept","Accept-Language","Content-Type","Origin","Referer"]

		# Prompt for folder to save responses
		outdir = input(Fore.CYAN + "\n[*] Enter folder name to save responses (Default: responses): " + Style.RESET_ALL).strip()
		if not outdir:
			outdir = "responses"

		if not multiple:
			combo = tuple(values_dict[k][0] for k in ordered)
			print(Fore.MAGENTA + "\n[*] Sending single request..." + Style.RESET_ALL)
			attack_start_time = time.time()
			send_requests_concurrent(method, path, headers, body, [combo], ordered, outdir, session_headers, original_placeholders, max_workers=1, start_time=attack_start_time)
		else:
			# Attack mode selection
			if len(ordered) == 1:
				attack_mode = "Sniper"
				print(Fore.YELLOW + f"\nOnly one parameter detected — using attack mode: {attack_mode}" + Style.RESET_ALL)
			else:
				print(Fore.YELLOW + "\n[*] Select attack mode:" + Style.RESET_ALL)
				print("1. Sniper")
				print("2. Clusterbomb ")
				print("3. Pitchfork")
				print("4. Battering-ram")
				choice = input("> Enter attack mode number: ").strip()
				if choice == "1":
					attack_mode = "Sniper"
				elif choice == "3":
					attack_mode = "Pitchfork"
				elif choice == "4":
					attack_mode = "Battering-ram"
				else:
					attack_mode = "Clusterbomb"

			try:
				combos, ordered_keys = generate_combos_from_values(values_dict, attack_mode)
			except Exception as e:
				print(Fore.RED + f"Error generating combos: {e}" + Style.RESET_ALL)
				return
			print(Fore.MAGENTA + f"\n[*] Total requests to send: {len(combos)} using {attack_mode}" + Style.RESET_ALL)
			attack_start_time = time.time()
			send_requests_concurrent(method, path, headers, body, combos, ordered_keys, outdir, session_headers, original_placeholders, max_workers=MAX_WORKERS, start_time=attack_start_time)

	except KeyboardInterrupt:
		elapsed = time.time() - start_all
		print(Fore.YELLOW + f"\n[*] Execution interrupted. Elapsed time: {elapsed:.2f} s ({format_duration(elapsed)})" + Style.RESET_ALL)
		return
	except Exception as ex:
		elapsed = time.time() - start_all
		print(Fore.RED + f"\n[*] Fatal error: {ex}" + Style.RESET_ALL)
		print(Fore.CYAN + f"[*] Elapsed until error: {elapsed:.2f} s ({format_duration(elapsed)})" + Style.RESET_ALL)
		return

	end_all = time.time()
	elapsed = end_all - start_all
	print(Fore.CYAN + f"\n[*] Total script time: {elapsed:.2f} s ({format_duration(elapsed)})" + Style.RESET_ALL)


#====================MAIN CALL=====================================================

if __name__ == "__main__":
	ascii_art = r"""
					 _____ __   _ _______  ______ _     _ ______   ______
					   |   | \  |    |    |_____/ |     | |     \ |_____/	
					 __|__ |  \_|    |    |    \_ |_____| |_____/ |    \_
			
					
					<<<<<<<<<<<<<<<<--------------------->>>>>>>>>>>>>>>>						                                 
	"""
	print(Fore.LIGHTRED_EX + "\n"*2 + ascii_art + Style.RESET_ALL)
	print(Fore.LIGHTCYAN_EX +"\n"+ " " * 60 + "Created by: MohammedAbdulAhadSaud\n" + Style.RESET_ALL)
	print(Fore.LIGHTYELLOW_EX + " " * 60 + "GitHub: https://github.com/MohammedAbdulAhadSaud/Intrudr\n" + Style.RESET_ALL)
	main()
