"""
=============================================================================
Safe-Trade AI: EasyOCR Custom Model Transfer Learning (Fine-tuning) Guide
=============================================================================

이 스크립트는 신분증 또는 사업자등록증과 같은 도메인 특화 이미지의 텍스트 인식률을
극대화하기 위해 EasyOCR(주로 Recognition 모델)을 전이학습(Fine-tuning)하는 가이드 및 코드 템플릿입니다.

EasyOCR의 내부 모델 구조는 CRAFT(글자 검출) + CRNN(글자 인식)으로 구성되어 있습니다.
대부분의 한국어 신분증 파인튜닝은 'CRNN(Recognition)' 모델 학습을 의미합니다.

[학습 아키텍처 및 단계 요약]
1. 데이터 세트 준비: 학습할 글자 이미지 파일과 라벨 파일(gt.txt) 생성.
2. LMDB 데이터 형식 변환: 빠른 데이터 로딩을 위해 LMDB로 가공.
3. 사전 학습된 한국어 모델(korean_g2.pth) 다운로드 및 로드.
4. Deep-Text-Recognition-Benchmark 훈련 스크립트로 학습 실행.
5. 학습 완료된 .pth 파일을 EasyOCR에서 불러오기.
"""

import os
import sys

def print_fine_tuning_guide():
    guide = """
## 1. 사전 준비 (Prerequisites)
전이학습을 진행하기 위해서는 EasyOCR의 기반 프로젝트인 Deep-Text-Recognition-Benchmark를 클론하고 의존성을 설치해야 합니다.

```bash
git clone https://github.com/JaidedAI/EasyOCR.git
cd EasyOCR/trainer
pip install -r requirements.txt
```

## 2. 학습 데이터셋 구축 (Dataset Structure)
학습 이미지를 저장할 폴더를 구성하고 이미지 파일 경로와 텍스트 라벨을 매핑하는 `gt.txt` 파일을 작성합니다.

예시 폴더 구조:
/data
    /train
        image_1.png
        image_2.png
        gt.txt
    /validation
        image_3.png
        gt.txt

`gt.txt` 내용 구성 방식 (탭문자 `\\t`로 이미지 경로와 정답 라벨 구분):
```text
train/image_1.png\\t홍길동
train/image_2.png\\t120-81-12345
```

## 3. LMDB 데이터 포맷 변환 (Create LMDB)
딥러닝 학습 시 입출력 속도(I/O) 성능 향상을 위해 LMDB 포맷으로 변환합니다.
EasyOCR의 `create_lmdb_dataset.py`를 실행합니다:

```bash
python create_lmdb_dataset.py \\
    --inputPath data/train/ \\
    --gtFile data/train/gt.txt \\
    --outputPath data_lmdb/train/

python create_lmdb_dataset.py \\
    --inputPath data/validation/ \\
    --gtFile data/validation/gt.txt \\
    --outputPath data_lmdb/validation/
```

## 4. 학습 시작 (Transfer Learning)
사전 학습된 한국어 가중치(korean_g2.pth)를 다운로드한 후, 전이학습을 실행합니다.

```bash
python train.py \\
    --train_data data_lmdb/train \\
    --valid_data data_lmdb/validation \\
    --select_data / \\
    --batch_ratio 1.0 \\
    --Transformation TPS --FeatureExtraction ResNet --SequenceModeling BiLSTM --Prediction CTC \\
    --saved_model custom_korean_g2.pth \\
    --FT
```
* `--FT` 옵션이 전이학습(Fine-tuning) 모드를 활성화하며, 기존 모델의 가중치를 베이스로 학습시킵니다.

## 5. 학습된 커스텀 모델을 EasyOCR 서비스에 로드하기 (Integration)
학습이 끝난 후 생성된 `.pth` 가중치 파일을 프로젝트 내 서비스에 등록하여 사용합니다.
    """
    print(guide)


# 아래 코드는 학습 완료된 커스텀 모델을 EasyOCRService에서 교체하여 로드하는 예시 코드입니다.
def load_custom_ocr_example(custom_model_path: str, custom_model_name: str):
    """
    [예시] 커스텀 학습 가중치(.pth)를 EasyOCR에 등록하고 불러오는 방법
    """
    import easyocr
    
    # 1. EasyOCR 사용자 디렉토리(~/.EasyOCR/user_network/) 경로 파악
    # 2. custom_model_name.pth 파일을 user_network 아래 저장
    # 3. custom_model_name.yaml 설정 파일 생성 (네트워크 레이어 명세 정의)
    
    # user_network_directory 지정 및 모델 이름 지정을 통해 전이학습 모델 적용
    reader = easyocr.Reader(
        lang_list=['ko', 'en'],
        rec_network=custom_model_name, # 학습 완료한 custom 모델의 이름 (확장자 제외)
        model_storage_directory=os.path.dirname(custom_model_path),
        user_network_directory=os.path.dirname(custom_model_path)
    )
    return reader

if __name__ == "__main__":
    print_fine_tuning_guide()
