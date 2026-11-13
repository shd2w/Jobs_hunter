---
task_id: "WP-00-01"
gate_id: "install_from_lock"
label: "automated-test"
status: "passed"
agent_label: "unlabelled-agent"
commit: "83c423f55ca6c055c785ed2de31d158c765b4122"
tree_dirty: true
source_fingerprint: "edc40f31b2e3e4f4ccd14176e5ee0e669f661dd17d612debc4e9666d3f19444d"
command: "python -m pip install --require-hashes -r requirements.txt"
environment: "Windows 11; python 3.12.8"
verdict_rationale: "exit code 0"
command_id: "install_from_lock"
exit_code: 0
output_ref: "inline below"
redactions: 0
timestamp: "2026-11-13T13:29:25+02:00"
---

```
Requirement already satisfied: annotated-types==0.8.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 7)) (0.8.0)
Requirement already satisfied: anyio==4.16.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 11)) (4.16.0)
Requirement already satisfied: beautifulsoup4==4.15.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 18)) (4.15.0)
Requirement already satisfied: brotli==1.2.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 24)) (1.2.1)
Requirement already satisfied: certifi==2026.10.23 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 169)) (2026.10.23)
Requirement already satisfied: cffi==2.1.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 178)) (2.1.1)
Requirement already satisfied: charset-normalizer==3.5.2 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 283)) (3.5.2)
Requirement already satisfied: cryptography==50.0.2 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 457)) (50.0.2)
Requirement already satisfied: cssselect2==0.10.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 518)) (0.10.1)
Requirement already satisfied: curl-cffi==0.17.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 522)) (0.17.0)
Requirement already satisfied: distro==1.9.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 557)) (1.9.0)
Requirement already satisfied: et-xmlfile==2.0.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 561)) (2.0.0)
Requirement already satisfied: fonttools==4.68.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from fonttools[woff]==4.68.0->-r requirements.txt (line 565)) (4.68.0)
Requirement already satisfied: google-auth==2.62.2 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from google-auth[requests]==2.62.2->-r requirements.txt (line 632)) (2.62.2)
Requirement already satisfied: google-genai==3.3.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 636)) (3.3.0)
Requirement already satisfied: h11==0.16.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 640)) (0.16.0)
Requirement already satisfied: h2==4.4.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 646)) (4.4.1)
Requirement already satisfied: hpack==4.2.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 650)) (4.2.0)
Requirement already satisfied: httpcore==1.0.9 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 654)) (1.0.9)
Requirement already satisfied: httpcore2==2.16.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 658)) (2.16.0)
Requirement already satisfied: httpx==0.28.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from httpx[http2]==0.28.1->-r requirements.txt (line 662)) (0.28.1)
Requirement already satisfied: httpx2==2.16.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 666)) (2.16.0)
Requirement already satisfied: hyperframe==6.1.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 670)) (6.1.0)
Requirement already satisfied: idna==3.20 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 674)) (3.20)
Requirement already satisfied: markdown-it-py==4.3.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 682)) (4.3.0)
Requirement already satisfied: markdownify==1.2.3 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 686)) (1.2.3)
Requirement already satisfied: mdurl==0.1.2 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 690)) (0.1.2)
Requirement already satisfied: numpy==2.5.4 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 694)) (2.5.4)
Requirement already satisfied: openpyxl==3.1.5 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 764)) (3.1.5)
Requirement already satisfied: pandas==3.1.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 768)) (3.1.1)
Requirement already satisfied: pillow==13.0.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 830)) (13.0.0)
Requirement already satisfied: pyasn1==0.6.5 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 915)) (0.6.5)
Requirement already satisfied: pyasn1-modules==0.4.2 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 919)) (0.4.2)
Requirement already satisfied: pycparser==3.12 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 923)) (3.12)
Requirement already satisfied: pydantic==2.14.3 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 927)) (2.14.3)
Requirement already satisfied: pydantic-core==2.50.4 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 934)) (2.50.4)
Requirement already satisfied: pydyf==0.13.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1076)) (0.13.0)
Requirement already satisfied: pygments==2.21.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1080)) (2.21.0)
Requirement already satisfied: pyphen==0.18.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1084)) (0.18.1)
Requirement already satisfied: python-dateutil==4.0.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1088)) (4.0.0)
Requirement already satisfied: python-dotenv==1.2.4 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1092)) (1.2.4)
Requirement already satisfied: python-jobspy==1.4.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1096)) (1.4.1)
Requirement already satisfied: pyyaml==6.0.3 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1100)) (6.0.3)
Requirement already satisfied: requests==2.34.2 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1175)) (2.34.2)
Requirement already satisfied: rich==15.0.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1182)) (15.0.0)
Requirement already satisfied: six==1.17.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1186)) (1.17.0)
Requirement already satisfied: sniffio==1.3.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1190)) (1.3.1)
Requirement already satisfied: soupsieve==4.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1194)) (4.1)
Requirement already satisfied: tenacity==9.1.4 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1198)) (9.1.4)
Requirement already satisfied: tinycss2==1.5.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1202)) (1.5.1)
Requirement already satisfied: tinyhtml5==2.1.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1208)) (2.1.0)
Requirement already satisfied: truststore==0.10.5 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1212)) (0.10.5)
Requirement already satisfied: typing-extensions==4.16.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1218)) (4.16.0)
Requirement already satisfied: typing-inspection==0.4.5 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1229)) (0.4.5)
Requirement already satisfied: tzdata==2026.6 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1233)) (2026.6)
Requirement already satisfied: urllib3==2.8.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1239)) (2.8.0)
Requirement already satisfied: weasyprint==70.0 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1243)) (70.0)
Requirement already satisfied: webencodings==0.6.1 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1247)) (0.6.1)
Requirement already satisfied: websockets==17.4 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1254)) (17.4)
Requirement already satisfied: zopfli==0.4.3 in C:\Users\ashad\AppData\Local\Temp\opencode\wp0001-proof-venv\Lib\site-packages (from -r requirements.txt (line 1410)) (0.4.3)
```
