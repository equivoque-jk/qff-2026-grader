# QFF 2026 Grader

**Qiskit Fall Fest · QUICK · 고려대학교**

Q-LINK 문제지 v4의 회로와 수치 답안을 채점하는 Python 패키지입니다. 참가자는 노트북에서 점수를 확인하고 제출 ZIP을 만들며, 운영진은 같은 패키지로 제출 데이터를 재채점합니다. 기본 문항은 **100점**, 선택 심화는 **추가 20점**입니다.

**[참가자용 문제지](https://github.com/equivoque-jk/qff-2026-Challenge-Quiz)** · [Google Colab에서 열기](https://colab.research.google.com/github/equivoque-jk/qff-2026-Challenge-Quiz/blob/main/QFF_Challenge_Colab.ipynb) · [Grader 2.0.4 다운로드](https://github.com/equivoque-jk/qff-2026-grader/releases/tag/v2.0.4)

## 참가자 안내

1. 참가자용 저장소에서 **`QFF_Challenge_Colab.ipynb`**를 내려받거나 Colab에서 열어 자신의 사본으로 저장하세요. 문제 설명, 이미지, 실험 코드와 설치 셀이 모두 이 파일에 들어 있습니다.
2. **준비 A 셀을 먼저 실행**하세요. Grader 2.0.4와 필요한 패키지가 자동으로 설치됩니다. 재시작 안내가 나오면 세션 또는 커널을 재시작하고 준비 A를 다시 실행하세요.
3. 준비 B·C·D와 문제 셀을 순서대로 실행하며, 23개 답안 함수의 **`TODO BEGIN`과 `TODO END` 사이**를 작성하세요. 함수 선언, 제공된 초기화 코드, 마지막 `return`, 실행·채점 셀은 그대로 두세요.
4. 제출할 때는 답안을 저장하고 **모두 실행 / Run All**을 선택하세요. 마지막 셀의 기본·추가 점수와 문항별 피드백을 확인하세요.

수치 답안은 문제에서 요구하는 정확한 값을 계산해 반환합니다. 4096-shot 관찰 결과와 구분하며, 채점 절대 허용오차는 `1e-6`입니다. 실험 메모와 서술 답안은 자동 점수에 포함되지 않습니다. 자세한 형식과 부분 점수 기준은 [함수 반환 계약](docs/RETURN_CONTRACTS.md)과 [배점표](docs/SCORING.md)를 참고하세요.

## 제출 파일 저장

마지막 채점 셀은 실행마다 새 ID로 제출 ZIP을 만듭니다.

| 실행 환경 | 제출 ZIP 저장 방법 |
|---|---|
| Google Colab | 마지막 셀이 브라우저에 자동 다운로드를 요청합니다. |
| Jupyter | 새로 실행한 마지막 셀의 **제출 ZIP 다운로드** 링크를 누르세요. |
| VS Code | 마지막 셀에 표시된 경로에 ZIP이 로컬 파일로 저장됩니다. |

ZIP에는 `submission.json`, `result.json`, `result.csv`, `manifest.json`이 들어 있습니다. 작성한 노트북은 ZIP에 포함되지 않으므로 **제출 ZIP과 작성한 `.ipynb`를 함께 제출**하세요. Colab에서는 런타임을 종료하기 전에 두 파일을 내려받으세요. 다시 채점했다면 마지막 출력의 실행 ID와 제출 ZIP이 일치하는지 확인하세요.

**제출처·마감 시각·제출 단위(개인/팀)·파일명 규칙·문의 채널은 행사 공지에 따릅니다.** 채점과 파일 저장만으로 제출이 접수되지는 않습니다.

## 실행 환경

Colab, VS Code, Jupyter에서 사용할 수 있습니다. Python **3.10–3.13**을 지원하며 로컬 환경은 **Python 3.12**를 권장합니다. 최초 설치에는 인터넷 연결이 필요합니다. 채점 계산에는 IBM 계정, API 키나 외부 채점 서버가 필요하지 않습니다.

- 설치가 실패하면 준비 A의 오류 메시지와 인터넷 연결을 확인한 뒤 다시 실행하세요.
- 세션이나 커널을 재시작하면 변수와 함수 정의가 사라집니다. 준비 A부터 필요한 셀을 순서대로 다시 실행하세요.
- 제공된 고장 회로의 실패 메시지와 자신의 답안에 대한 채점 결과를 구분하세요. 2-1과 선택 2-5의 고장 회로는 결함을 찾기 위한 실험입니다.

## 운영진 설치 및 재채점

참가자용 문제지와 같은 **Grader 2.0.4**를 설치합니다. 배포 파일의 SHA-256은 [Release의 `SHA256SUMS.txt`](https://github.com/equivoque-jk/qff-2026-grader/releases/download/v2.0.4/SHA256SUMS.txt)에서 확인할 수 있습니다.

```sh
python -m pip install "https://github.com/equivoque-jk/qff-2026-grader/releases/download/v2.0.4/qff_local_grader-2.0.4-py3-none-any.whl"
qff-grade --version
qff-grade-batch --version
```

답안 JSON 하나를 재채점하려면 다음 명령을 사용합니다.

```sh
qff-grade submission.json --output result.json --csv result.csv
```

여러 제출 ZIP 또는 JSON을 `received` 폴더에 모아 일괄 재채점할 수 있습니다. 결과 폴더는 입력 폴더 밖으로 지정하세요. 단일 ZIP도 이 명령으로 처리할 수 있습니다.

```sh
qff-grade-batch received --output grading_results
```

실행마다 새 결과 폴더에 전체 점수표 `scores.csv`, 요약 `summary.json`, 제출별 답안과 진단 기록을 저장합니다. 제출 ZIP과 그 안에서 추출한 JSON을 모두 넣으면 별개 제출로 처리하므로 한 형식만 넣으세요. 파일 수집, 오류 처리와 공식 성적 선정 절차는 [운영진 안내](docs/OPERATOR.md)에 있습니다.

운영진 재채점기는 참가자의 Python 코드나 노트북을 실행하지 않고 `submission.json`의 회로·수치 데이터를 검사합니다. 제출 ZIP 안의 점수표는 재채점 결과로 대체해 사용하며, 작성한 노트북은 풀이 과정 확인을 위해 함께 보관하세요.

문제지 실행에 필요한 시뮬레이션·시각화 도구를 운영진 환경에도 설치하려면 다음 명령을 사용합니다.

```sh
python -m pip install "qff-local-grader[notebook] @ https://github.com/equivoque-jk/qff-2026-grader/releases/download/v2.0.4/qff_local_grader-2.0.4-py3-none-any.whl"
```
