# 배포 체크리스트

## 코드
- [ ] `/health` 200
- [ ] `/speller` 200
- [ ] `/predict` 정상
- [ ] `MOCK_MODE=true`에서 pytest 통과
- [ ] `BCI_DEMO_MODE=true`에서 임의 입력 후보 생성
- [ ] Local LoRA import가 production 시작을 막지 않음

## 보안
- [ ] `.env` Git 제외
- [ ] 실제 OpenAI key 코드/HTML에 없음
- [ ] Render Secret으로 OPENAI_API_KEY 설정
- [ ] Usage/Spend limit 설정

## 발표
- [ ] ㅁㅈ → 물 줘
- [ ] ㅅㄹㅎ → 사랑해
- [ ] ㄷㅇㅈ + positioning → 도와줘
- [ ] ㄷㅇㅈ + schedule → 다음 주
- [ ] 문장 buffer
- [ ] TTS
- [ ] Decoder/SSVEP는 현재 UI simulation임을 명확히 설명
