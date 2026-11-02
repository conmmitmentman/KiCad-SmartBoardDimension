# 開発協力

対象はネイティブ版です。不具合報告にはKiCadの基準版、OS、ネイティブ版のリビジョン、再現操作、外形の種類を記載してください。未公開基板や個人情報は含めないでください。

変更時は日本語の説明と関連テストを更新してください。

```sh
python -m unittest discover -s native/tests -v
python -m unittest discover -s tests -v
```

C++コードはGPL-3.0-or-later、他のファイルは各ファイルのライセンスに従います。実機未確認の変更はその旨を明記してください。[ビルド手順](native/README.md)。
