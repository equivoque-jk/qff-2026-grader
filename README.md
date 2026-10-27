# QFF 2026 로컬 자동채점 — 패키지 2.0.3

QFF 2026 Q-LINK 문제지의 회로와 수치 답안을 채점하는 공개 Python 패키지입니다. 참가자는 Colab에서 답안을 채점하고 제출 ZIP을 만들며, 운영진은 같은 패키지로 제출 데이터를 다시 채점합니다. 기본 100점과 선택 심화 20점을 별도로 표시합니다.

현재 패키지는 **2.0.3**입니다. 문제지 ver3도 같은 2.0.3을 사용합니다. 이 저장소에는 채점기 소스와 반환 계약·배점·운영 안내를 공개합니다. 참가자용 문제지는 운영진이 별도로 배포합니다.

## 설치

[Release v2.0.3](https://github.com/equivoque-jk/qff-2026-grader/releases/tag/v2.0.3)에서 wheel과 소스 배포 파일을 제공합니다. 2.0.3에서는 JupyterLab에서 제출 ZIP 링크를 누르면 텍스트 편집기로 열려 UTF-8 오류가 나던 문제를 수정했습니다. 실행 후 표시되는 링크는 브라우저에 ZIP 다운로드를 요청합니다. Colab의 자동 다운로드와 ZIP 생성 방식은 그대로입니다. 배점과 답안 판정 기준은 동일합니다.

운영진 재채점이나 일반 Python 환경에서는 다음 명령으로 설치합니다. 버전이 고정된 wheel URL을 사용합니다. 배포 파일의 SHA-256은 같은 Release의 `SHA256SUMS.txt`에서 확인할 수 있으며, 참가자용 문제지의 설치 셀에는 wheel 해시도 고정합니다.

```sh
python -m pip install "https://github.com/equivoque-jk/qff-2026-grader/releases/download/v2.0.3/qff_local_grader-2.0.3-py3-none-any.whl"
qff-grade --version
qff-grade-batch --version
```

문제지의 회로 그림·시뮬레이션 도구까지 설치하려면 `notebook` 추가 의존성을 사용합니다.

```sh
python -m pip install "qff-local-grader[notebook] @ https://github.com/equivoque-jk/qff-2026-grader/releases/download/v2.0.3/qff_local_grader-2.0.3-py3-none-any.whl"
```

Python 3.10–3.13을 대상으로 하며 로컬 권장 버전은 Python 3.12입니다. Qiskit 2.3.1, NumPy 2.2.6, psutil 7.2.2를 고정합니다. `notebook`에는 Aer 0.17.2, Matplotlib 3.10.8, pylatexenc 2.10, IPython 7.34 이상, nbformat 5 이상을 포함합니다. 기존 2.0.1의 전체 실행은 macOS Python 3.12.14와 Colab Python 3.13.16에서 확인했습니다. 2.0.3의 별도 검증 범위는 Release 설명에 기록합니다.

최초 설치에는 인터넷이 필요하며, 설치 후 채점 계산에는 외부 서버나 계정·API 키가 필요하지 않습니다. Colab에서는 배포받은 노트북의 준비 A 안내를 따릅니다. 이미 불러온 수치 패키지를 교체해 재시작 안내가 나오면 **런타임 → 세션 다시 시작** 후 준비 A를 다시 실행합니다.

## 답안 작성과 채점

문제지에 준비된 23개 함수의 TODO를 작성하고 [반환 계약](docs/RETURN_CONTRACTS.md)에 맞는 회로 또는 수치를 반환합니다. 전체 답안을 채점할 때 노트북을 모두 실행하면 마지막 셀의 `finalize_submission(globals())`가 답안을 한 번 수집하고 같은 데이터로 채점·저장합니다.

- 기본 14문항은 100점, 선택 2문항은 추가 20점으로 총점 상한은 120점입니다.
- 독립된 세부 항목별로 부분점수를 부여합니다. 미작성·오답·확인할 수 없는 항목은 0점이며, 다른 독립 항목의 점수는 유지합니다.
- 수치 답안은 이상적 회로의 정확한 값이며 절대 허용오차는 `1e-6`입니다. 관찰용 4096-shot 추정값과 구분합니다.
- 실험 메모와 서술 답안은 자동 점수에 포함하지 않습니다.

상세 배점은 [배점표](docs/SCORING.md)에 있습니다. 명령으로도 같은 배점표를 확인할 수 있습니다.

```sh
qff-grade --rubric
```

## 제출 파일과 운영진 재채점

노트북의 마지막 셀은 실행마다 새 ID로 제출 ZIP을 만듭니다. ZIP에는 `submission.json`, `result.json`, `result.csv`, `manifest.json`을 넣습니다. 작성한 노트북은 자동 포함되지 않으므로 **제출 ZIP과 `.ipynb`를 공지된 제출처에 함께 제출**합니다. 로컬 채점·다운로드 완료는 공식 접수가 아닙니다.

운영진은 참가자가 보낸 점수 파일을 사용하지 않고 `submission.json`의 회로·수치 데이터를 다시 계산합니다. JSON 한 개는 다음과 같이 채점합니다.

```sh
qff-grade submission.json --output result.json --csv result.csv
```

여러 제출 ZIP 또는 JSON을 `received` 폴더에 모았다면 다음 명령을 사용합니다. 결과 폴더는 입력 폴더 밖으로 지정합니다.

```sh
qff-grade-batch received --output grading_results
```

각 실행은 새 결과 폴더에 전체 점수표 `scores.csv`, 요약 `summary.json`, 제출별 답안·결과·감사 기록을 저장합니다. 이전 실행 기록은 덮어쓰지 않습니다. 제출 ZIP과 추출한 JSON을 함께 넣으면 두 건으로 처리하므로 한 형식만 넣습니다.

팀 신원과 마감 시각은 공식 제출처의 접수 기록으로 확인합니다. 클라이언트가 적은 팀 ID·생성 시각은 인증 자료가 아니며, 팀별 최종 유효 제출은 행사 정책에 따라 운영진이 선택합니다. 자세한 입력 제한과 오류 처리는 [운영진 안내](docs/OPERATOR.md)를 참고하세요.

## 공개 채점기의 범위

채점 기준과 구현은 공개되어 있습니다. 운영진 재채점기는 참가자의 Python 소스나 노트북을 실행하지 않고 구조화된 QPY 회로와 JSON 수치 데이터를 검증합니다. 반환값 채점만으로 풀이 과정이나 하드코딩 여부까지 확인할 수 없으므로 작성 노트북도 함께 보관합니다.

이 저장소에는 참조 답안, 개인 제출 파일, 검증 실행 기록을 포함하지 않습니다. 공개 소스의 `qff_grader` 파일은 Release 2.0.3의 실행 코드와 같습니다.
