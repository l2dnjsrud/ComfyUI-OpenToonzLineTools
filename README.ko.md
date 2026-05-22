# ComfyUI OpenToonz Line Tools

[English README](README.md)

러프한 블루 만화/웹툰 원고를 위한 OpenToonz 아이디어 기반 ComfyUI 커스텀 노드입니다.

이 프로젝트는 **OpenToonz 전체 앱을 임베드하거나 C++ 코드를 그대로 포팅하지 않습니다.**
현재 스케치-to-컬러 연구에 필요한 제작 아이디어만 가볍게 가져옵니다.

- 스캔 원고식 블루 선 정리
- 채색 전에 열린 선/gap 자동 보정
- 이후 색 보정을 위한 region/palette map 생성

목표 흐름은 다음과 같습니다.

```text
블루 러프 패널 crop
  -> OT Blue Line Cleanup
  -> OT Line AutoClose
  -> OT Region Palette Map
  -> Qwen Image Edit / MangaNinja / reference colorization
  -> panel reassemble
```

## 왜 이 기능인가

OpenToonz의 강점은 전통 2D 애니메이션의 cleanup, ink/paint, palette 관리,
compositing입니다. 현재 연구에 필요한 것은 UI나 타임라인이 아니라, 러프 원고를
채색 가능한 상태로 만드는 저수준 선 정리 단계입니다.

참고한 OpenToonz 문서:

- [Cleaning-up Scanned Drawings](https://opentoonz.readthedocs.io/en/latest/cleaning-up_scanned_drawings.html)
- [Painting Animation Levels](https://opentoonz.readthedocs.io/en/latest/painting_animation_levels.html)
- [Managing Palettes and Styles](https://opentoonz.readthedocs.io/en/latest/managing_palettes_and_styles.html)
- [OpenToonz source tree](https://github.com/opentoonz/opentoonz/tree/master/toonz/sources)

## 노드

### OT Blue Line Cleanup

블루 러프 연필선을 분류하고, 검은 선/흰 배경 형태의 정규화된 line image와 overlay
preview를 만듭니다.

출력:

- `clean_line`: 검출된 선을 검정으로 만든 흰 배경 이미지
- `line_overlay`: 원본 위에 검출 stroke를 빨간색으로 표시한 preview
- `transparent_line_preview`: 투명 line 출력을 흰 배경에서 확인하는 preview
- `settings_json`: 사용한 파라미터

### OT Line AutoClose

line skeleton의 endpoint를 찾고, 거리와 방향이 맞는 짧은 gap을 자동으로 닫습니다.

출력:

- `closed_line`: gap closure 후 line image
- `closure_overlay`: 원래 선은 검정, 새로 닫은 선은 빨강으로 표시
- `segments_json`: 닫은 segment 좌표

### OT Region Palette Map

line art로 분리된 fillable region을 labeling하고 region metadata JSON을 반환합니다.
OpenToonz식 indexed color editing으로 가기 위한 첫 단계입니다.

출력:

- `region_preview`: region label을 색으로 표시한 preview
- `regions_json`: 각 region의 bbox, area, centroid, style id

## 설치

이 폴더를 ComfyUI custom nodes에 연결합니다.

```bash
cd /Users/iwongyeong/AI/ComfyUI/custom_nodes
ln -s /Users/iwongyeong/AI/ComfyUI-OpenToonzLineTools ComfyUI-OpenToonzLineTools
```

필요하면 ComfyUI 환경에 의존성을 설치합니다.

```bash
cd /Users/iwongyeong/AI/ComfyUI
source .venv/bin/activate
pip install -r /Users/iwongyeong/AI/ComfyUI-OpenToonzLineTools/requirements.txt
deactivate
```

ComfyUI를 재시작하면 다음 카테고리에 노드가 나타납니다.

```text
manga/opentoonz-line-tools
```

## 검증

ComfyUI Python 환경으로 smoke test를 실행합니다.

```bash
cd /Users/iwongyeong/AI/ComfyUI-OpenToonzLineTools
/Users/iwongyeong/AI/ComfyUI/.venv/bin/python -m unittest discover -s tests -v
```

## 현재 범위

구현됨:

- OpenToonz 아이디어 기반 블루 cleanup baseline
- endpoint 기반 line autoclose
- fillable region labeling 및 palette preview JSON
- ComfyUI node wrapper
- 영어/한국어 문서와 시각화 문서

아직 구현하지 않음:

- OpenToonz C++ 직접 바인딩
- TLV/PLI 파일 지원
- 완전한 palette-index raster format
- semantic inking 또는 AI colorization model 자체

## 추천 다음 실험

현재 Mr.Blue v5 polygon crop을 입력으로 사용해서 다음을 비교합니다.

1. raw crop -> Qwen Image Edit,
2. cleanup crop -> Qwen Image Edit,
3. cleanup + autoclose + region map -> reference colorization/correction.

성공 기준은 blue-line 제거, 구도 유지, fill leak 감소, palette/region JSON이 후처리
수정에 실제로 도움이 되는지입니다.
