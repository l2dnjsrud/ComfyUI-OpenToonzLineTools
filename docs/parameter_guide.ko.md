# 노드와 파라미터 가이드

이 문서는 ComfyUI에 보이는 쉬운 표시 이름 기준입니다. workflow 호환을 위해
내부 node id는 그대로 유지합니다.

- `OTBlueLineCleanup` -> `Blue Sketch Cleaner`
- `OTLineAutoClose` -> `Line Gap Closer`
- `OTRegionPaletteMap` -> `Color Region Finder`

추천 흐름:

```text
패널 crop
  -> Blue Sketch Cleaner
  -> Line Gap Closer
  -> Color Region Finder
  -> 채색 / 색 보정
```

전체 페이지에는 먼저 패널 검출과 crop을 거친 뒤 쓰는 것이 좋습니다. MC/MS
전체 페이지는 gap closing과 region map의 기본 입력으로는 너무 복잡합니다.

## Blue Sketch Cleaner

첫 번째로 쓰는 노드입니다. 파란 러프 연필선을 검출해서 흰 배경의 검은 line
art로 바꿉니다.

출력:

- `clean_line`: 흰 배경 위 검은 line art.
- `line_overlay`: 원본 위에 검출된 파란 stroke를 빨간색으로 표시.
- `transparent_line_preview`: line-only preview를 흰 배경에서 확인.
- `settings_json`: 설정값과 이미지별 line 통계.

파라미터:

| Parameter | Default | 사용법 |
|---|---:|---|
| `hue_low` | 90 | OpenCV HSV 기준 파란색 hue 하한입니다. 범위는 `0-179`. 청록 계열 선이 빠지면 낮춥니다. |
| `hue_high` | 145 | 파란색 hue 상한입니다. 보라빛 파란 선이 빠지면 올립니다. |
| `saturation_min` | 28 | 색의 진함 최소값입니다. 배경 잡음이 잡히면 올리고, 흐린 파란 연필선이 빠지면 낮춥니다. |
| `value_min` | 20 | 밝기 최소값입니다. 어두운 파란 선이 빠지면 낮추고, 그림자/노이즈가 잡히면 올립니다. |
| `include_dark_lines` | false | 검은색/어두운 선도 같이 포함합니다. 파란 선과 검은 선이 섞인 패널에 유용하지만 글자, 컷선, 그림자도 같이 잡힐 수 있습니다. |
| `despeckle_px` | 8 | 이 픽셀 면적보다 작은 점 노이즈를 제거합니다. 먼지 제거는 올리고, 작은 의도된 선이 사라지면 낮춥니다. |
| `close_px` | 1 | 작은 틈을 붙이는 morphology closing 반경입니다. 올리면 미세한 끊김은 줄지만 선이 두꺼워지거나 붙을 수 있습니다. |

시작값:

- 파란 러프만 있는 경우: 기본값.
- 파란 선이 너무 흐림: `saturation_min 15-25`, `value_min 10-20`.
- 배경이 너무 많이 잡힘: `saturation_min 45-70`, `despeckle_px 16-64`.
- 파란 선과 검은 선이 섞임: `include_dark_lines true`, overlay를 꼭 확인.

## Line Gap Closer

`Blue Sketch Cleaner` 뒤에 쓰는 노드입니다. line art를 skeleton으로 줄이고,
endpoint를 찾은 뒤 방향과 거리가 맞는 짧은 gap을 닫습니다.

출력:

- `closed_line`: gap closing 후 line art.
- `closure_overlay`: 원래 선은 검정, 새로 닫은 gap은 빨강.
- `segments_json`: 이미지별 닫은 segment 좌표와 skip 이유.

파라미터:

| Parameter | Default | 사용법 |
|---|---:|---|
| `threshold` | 180 | 이 값보다 어두운 픽셀을 선으로 봅니다. 검은 선만 엄격히 잡으려면 낮추고, 회색 선이 빠지면 올립니다. |
| `closing_distance` | 18 | endpoint끼리 연결할 최대 거리입니다. 큰 gap을 닫으려면 올리고, 엉뚱한 선끼리 붙으면 낮춥니다. |
| `spot_angle` | 75 | 방향 허용 각도입니다. 낮추면 엄격해지고, 높이면 더 많은 애매한 gap을 닫습니다. |
| `line_width` | 1 | 새로 그리는 closure stroke 두께입니다. line art에는 보통 `1-2`가 적당합니다. |
| `max_endpoints` | 600 | 안전 제한입니다. endpoint가 너무 많으면 무리하게 닫지 않고 skip합니다. 전체 페이지는 자주 이 제한을 넘습니다. |

시작값:

- 패널 crop: 기본값.
- 아주 작은 끊김만 닫기: `closing_distance 8-12`, `spot_angle 45-60`.
- 러프한 큰 gap도 닫기: `closing_distance 20-32`, `spot_angle 75-100`.
- 전체 페이지: 기본적으로 피하세요. 실험용으로만 overlay를 보면서 `max_endpoints`를 올립니다.

## Color Region Finder

gap closing 뒤에 쓰는 노드입니다. 검은 line art로 둘러싸인 흰 영역을 찾아
채색 가능한 region preview를 만듭니다.

출력:

- `region_preview`: 검출 region을 색으로 표시하고 line art는 검정으로 표시.
- `regions_json`: 각 region의 bbox, area, centroid, style id.

파라미터:

| Parameter | Default | 사용법 |
|---|---:|---|
| `threshold` | 180 | 이 값보다 어두운 픽셀을 region 경계선으로 봅니다. Line Gap Closer와 맞춰 쓰는 것이 좋습니다. |
| `min_area` | 32 | 이 픽셀 면적보다 작은 region을 무시합니다. 노이즈가 많으면 올리고, 눈/장식 같은 작은 영역이 빠지면 낮춥니다. |
| `max_regions` | 128 | 이미지당 반환할 최대 region 수입니다. 복잡한 패널은 올릴 수 있지만, 항상 cap에 걸리면 입력이 너무 큽니다. |
| `ignore_border_regions` | true | 이미지 경계에 닿은 열린 region을 무시합니다. 패널 crop에는 true 권장, 페이지/레이아웃 디버깅에는 false도 가능. |

시작값:

- 패널 crop: 기본값.
- 작은 색 조각이 너무 많음: `min_area 128-512`.
- 눈/소품/장식이 빠짐: `min_area 8-24`.
- 전체 페이지 디버그: `max_regions 512+`, 대신 매우 noisy할 수 있습니다.

## 빠른 판정법

- `Blue Sketch Cleaner` overlay가 맞으면 hue/saturation 설정은 대체로 맞습니다.
- `Line Gap Closer`가 `endpoint_count_exceeded`를 내면 더 작게 crop한 뒤 쓰세요.
- `Color Region Finder`가 항상 `max_regions`와 같은 region 수를 내면 이미지가 너무 복잡하거나 열린 선이 많다는 뜻입니다.
