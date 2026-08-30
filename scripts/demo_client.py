import json
import requests

payload = {
    "input_mode": "initials",
    "bci_input": "ㄷㅇㅈ",
    "partner": "family",
    "situation": "home",
    "current_sentence": "",
    "recent_context": ["혼자 자세를 바꾸기 어렵다"],
    "top_k": 3,
}

response = requests.post("http://127.0.0.1:8000/predict", json=payload, timeout=20)
response.raise_for_status()
print(json.dumps(response.json(), ensure_ascii=False, indent=2))
