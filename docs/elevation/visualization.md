# Visualization Elevation Board

기준 시점: 2026-03-15

## 현재 목표
- raw point / filtered point / cluster / track를 공간적으로 바로 확인
- 발표용이 아니라 `디버그용`으로 빠르게 이상 징후를 찾기
- 오른쪽 레일이 있는 공장 레이아웃을 단순화해서 추적 결과를 직관적으로 보기

## 구현 및 REQ 목록

### 핵심 구조
- ~~실시간 3D 디버그 viewer baseline 구현~~
- ~~오른쪽 rail 고정 오브젝트 시각화 추가~~
- ~~raw / filtered / cluster / track를 서로 다른 색으로 구분~~
- ~~track id 텍스트 표시~~
- ~~live UART 파이프라인과 연결~~
- ~~direct script 실행 import 경로 보강~~
- ~~viewer 예외 날짜별 markdown 로그 기록~~

### 운영/품질
- max visualization FPS 제한
- rail 위치/크기 파라미터화
- 시야각 preset 2개 이상 제공
- replay 모드 추가
- track history trail 추가

### 발표/확장
- 컨베이어벨트 영역 overlay
- 제어 trigger 발생 시 색상 변경
- 객체별 상태(`tentative`, `confirmed`) 시각 반영
- 캡처/녹화용 시나리오 정리

## 실행 예시
```bash
python src/visualization/live_rail_viewer.py --cli-port COM11 --data-port COM10 --config config/profile_3d.cfg
```

## 한 줄 메모
- X축 양의 방향을 `오른쪽`으로 보고, 그쪽에 rail 박스를 배치한다.
- 이 viewer는 성능 측정용이 아니라 디버그 관찰용이다.

## 업데이트 로그
- 2026-03-15: 3D debug viewer와 right rail baseline 추가
- 2026-03-15: direct script import 경로 문제 수정, viewer 에러 로그 기록 추가
