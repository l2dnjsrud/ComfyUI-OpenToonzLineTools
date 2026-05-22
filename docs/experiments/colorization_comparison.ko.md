# 패널 채색 결과 비교

[English version](colorization_comparison.md)

날짜: 2026-05-22

이 실험은 OpenToonz 아이디어 기반 전처리가 실제 패널 채색 결과에 도움이 되는지
로컬 ComfyUI 환경에서 확인한 것입니다.

## 입력

패널 crop:

```text
/Users/iwongyeong/AI/outputs/MC-13/split_v4/panels
```

사용한 패널:

```text
panel_002.png
panel_003.png
panel_004.png
panel_005.png
panel_006.png
```

`panel_001.png`는 대부분 페이지 라벨/텍스트 조각이라 제외했습니다.

## 비교 입력

각 패널마다 비교 스크립트가 다음 산출물을 만들었습니다.

- `source`: resize된 원본 blue rough crop.
- `clean_line`: Blue Sketch Cleaner 출력.
- `closed_line`: Blue Sketch Cleaner 이후 Line Gap Closer 출력.
- `region_preview`: Color Region Finder 확인용 preview.
- `raw_color`, `clean_color`, `closed_color`: 선택한 ComfyUI workflow의 채색 결과.

## 테스트한 워크플로우

### Qwen Image Edit

Qwen Image Edit prompt queue까지는 성공했지만, 로컬 Apple Silicon MPS에서 sampling
중 실패했습니다. 설치된 `fp8mixed` Qwen 모델이 MPS가 지원하지 않는 float8 경로를
요구했습니다.

```text
Trying to convert Float8_e4m3fn to the MPS backend but it does not have support for that dtype.
```

이 경로는 CUDA/NVIDIA 환경에서 다시 시도하는 것이 맞습니다.

### SD1.5 Anything + Lineart ControlNet

출력:

```text
outputs/color_compare_mc13_split_v4_controlnet_v3_same_seed
```

이 workflow는 색은 강하게 넣지만 패널 구도를 자주 재해석했습니다. 일부 raw 또는
closed-line 변형은 완전히 검정으로 붕괴했습니다. 메인 연구 경로로 쓰기에는
아직 안정적이지 않습니다.

### SD1.5 Anything Img2Img

출력:

```text
outputs/color_compare_mc13_split_v4_img2img
```

이 workflow는 구도 보존이 더 낫습니다. raw blue crop은 blue artifact가 남는
경향이 있었고, `clean_line`과 `closed_line`은 blue signal을 대부분 제거했습니다.
하지만 캐릭터 정체성을 바꾸거나 `panel_004`처럼 완전히 실패하는 경우가 있습니다.

## 결과

로컬에서 테스트한 것 중 가장 나은 경로:

```text
panel crop -> Blue Sketch Cleaner -> Line Gap Closer -> img2img colorization
```

다만 production-ready는 아닙니다. 전처리 노드는 유용하지만, 현재 로컬 SD1.5
채색 workflow가 line-prep 노드보다 약합니다. 다음으로 가장 의미 있는 실험은
같은 clean/closed 패널 입력을 CUDA 환경의 Qwen Image Edit 또는 입력 구도 보존이
강한 다른 image-edit 모델에서 다시 돌리는 것입니다.

## 핵심 판단

- 이 노드들은 전체 페이지보다 panel crop 단위에서 맞습니다.
- Blue Sketch Cleaner는 채색 전에 유용합니다. raw blue line이 결과에 남거나 모델을
  나쁜 방향으로 유도할 수 있습니다.
- Line Gap Closer는 도움이 될 때도 있지만, seed와 sampler에 따라 과하게 제약을
  주거나 불안정한 생성을 만들 수 있습니다.
- Color Region Finder는 자동 의미 팔레트가 아니라 fill leak/debug preview로 보는
  것이 맞습니다.
- 현재 로컬 MPS에서는 fp8 Qwen Image Edit 모델을 실행할 수 없습니다.

