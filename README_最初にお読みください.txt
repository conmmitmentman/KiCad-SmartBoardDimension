スマート基板寸法 KiCad 10 / v1.2.0

【追加機能】KiCadのダイアログ内に「GitHubから更新」「更新元の設定」ボタンを追加しました。
初回だけGitHubリポジトリを登録し、その後は「GitHubから更新」を押せば確認・適用できます。
公開済みのGitHub Releaseが必要です。更新後はKiCad PCBエディタを再起動してください。

インストール: Windows_インストール.bat
既にインストール済みで更新: Windows_更新.bat
前のバージョンに戻す: Windows_前の版に戻す.bat

重要:
  1. ZIPをすべて展開し、KiCad PCBエディタを終了してから実行してください。
  2. 基板の .kicad_pcb ファイルをバックアップしてください。
  3. 完了後にKiCad PCBエディタを起動してください。
  4. ツール > 外部プラグイン > スマート基板寸法（幅・高さ）

対応: KiCad 10.x / Windows 10, 11 想定
制限: 軸に平行な長方形のEdge.Cuts外形のみ（複雑な外形は不可）
注意: 実際のKiCad 10上での動作試験は未実施です。
      配布ZIPは未署名です。信用できる公開元から取得してください。
      組織やWindowsの設定でPowerShellが禁止される場合は手動コピーしてください。

詳しい説明: README.md, docs/INSTALL_JA.md, docs/UPDATE_JA.md, docs/ONLINE_UPDATE_JA.md
