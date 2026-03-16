# Error Log Guide

이 폴더는 실행 중 발생한 오류를 날짜별 markdown 파일로 남기는 용도다.

규칙:

- 파일명: `YYYY-MM-DD.md`
- 같은 날짜에 새 오류가 발생하면 같은 파일 아래에 계속 추가
- 에러 로그에는 실행 명령, 포트 정보, cfg 경로, 예외 타입, traceback을 함께 기록

현재 `src/parser/tlv_parse_runner.py`는 기본적으로 예외 발생 시 이 폴더에 자동 기록한다.
