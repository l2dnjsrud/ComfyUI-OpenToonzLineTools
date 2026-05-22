# 시각화 파이프라인

[English version](visual_pipeline.md)

이 문서는 OpenToonz 아이디어 기반 line tools가 현재 rough-sketch-to-color 연구
파이프라인의 어디에 들어가는지 보여줍니다.

## 연구 내 위치

```mermaid
flowchart TD
    A[블루 원고 페이지] --> B[Mr.Blue YOLO-seg panel detector]
    B --> C[Polygon-masked panel crops]
    C --> D{Preprocess?}
    D -->|baseline| E[Raw crop to Qwen Image Edit]
    D -->|OT-inspired| F[Blue Sketch Cleaner]
    F --> G[Line Gap Closer]
    G --> H[Color Region Finder]
    H --> I[Qwen Image Edit or MangaNinja]
    E --> J[Colored panel]
    I --> J
    J --> K[Panel Reassemble]
```

## 노드 체인

```mermaid
flowchart LR
    A[Load Image / Panel Crop] --> B[Blue Sketch Cleaner]
    B --> C[Line Gap Closer]
    C --> D[Color Region Finder]
    D --> E[Colorization Node]
    E --> F[Reassemble]
```

## 출력 산출물

```mermaid
flowchart TD
    A[Blue Sketch Cleaner] --> A1[clean_line IMAGE]
    A --> A2[line_overlay IMAGE]
    A --> A3[settings_json]
    B[Line Gap Closer] --> B1[closed_line IMAGE]
    B --> B2[closure_overlay IMAGE]
    B --> B3[segments_json]
    C[Color Region Finder] --> C1[region_preview IMAGE]
    C --> C2[regions_json]
```

## 실험 매트릭스

| Variant | Color model 입력 | 기대 효과 | 위험 |
| --- | --- | --- | --- |
| A | raw panel crop | 가장 빠른 baseline | 블루 러프가 결과에 남을 수 있음 |
| B | clean line crop | blue noise 감소 | 의미 있는 러프 정보까지 제거할 수 있음 |
| C | clean line + autoclose | fill 안정성 증가 | 잘못된 closure line이 생길 수 있음 |
| D | clean line + autoclose + region JSON | 후처리 수정 용이 | downstream region-aware tooling 필요 |

현재 로컬 비교:

- [패널 채색 결과 비교](experiments/colorization_comparison.ko.md)
- 로컬 Apple Silicon에서는 `clean_line` / `closed_line`이 img2img 전에 blue rough
  artifact를 줄이는 데 도움이 됩니다.
- 현재 SD1.5 ControlNet workflow는 패널 보존보다 재해석 성향이 강합니다.
- 설치된 fp8 Qwen Image Edit 모델은 MPS float8 미지원 때문에 CUDA 환경에서 다시
  시도하는 것이 맞습니다.

## 채택 기준

아래 중 하나 이상이 명확히 좋아질 때 default 전처리로 채택합니다.

- 최종 결과의 blue artifact 감소,
- line boundary를 넘어가는 색 누수 감소,
- correction 이후 캐릭터/의상 색 일관성 향상,
- overlay/JSON으로 전처리 판단을 확인하기 쉬움.
