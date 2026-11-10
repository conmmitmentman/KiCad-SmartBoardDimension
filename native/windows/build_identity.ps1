# Identify an existing native build without running KiCad or changing its files.
# These compiled UI markers identify the feature; they are not a digital signature.

function Initialize-NativeMarkerScanner {
    if ('SmartBoardDimensionSetup.BinaryMarkers' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;

namespace SmartBoardDimensionSetup
{
    public static class BinaryMarkers
    {
        public static bool ContainsAll(string path, string[] markers)
        {
            if (markers == null || markers.Length == 0)
                throw new ArgumentException("At least one marker is required.");
            byte[][] patterns = new byte[markers.Length][];
            bool[] found = new bool[markers.Length];
            int maxLength = 0;
            for (int n = 0; n < markers.Length; n++)
            {
                if (String.IsNullOrEmpty(markers[n]))
                    throw new ArgumentException("Markers must not be empty.");
                patterns[n] = Encoding.Unicode.GetBytes(markers[n]);
                maxLength = Math.Max(maxLength, patterns[n].Length);
            }

            const int chunkSize = 3 * 1024 * 1024;
            int overlap = maxLength - 1;
            byte[] buffer = new byte[chunkSize + overlap];
            int carried = 0;
            int remaining = markers.Length;
            using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read,
                FileShare.Read, chunkSize, FileOptions.SequentialScan))
            {
                int read;
                while ((read = stream.Read(buffer, carried, chunkSize)) > 0)
                {
                    int length = carried + read;
                    for (int n = 0; n < patterns.Length; n++)
                    {
                        if (found[n]) continue;
                        byte[] pattern = patterns[n];
                        for (int i = 0; i <= length - pattern.Length; i++)
                        {
                            if (buffer[i] != pattern[0]) continue;
                            int j = 1;
                            while (j < pattern.Length && buffer[i + j] == pattern[j]) j++;
                            if (j != pattern.Length) continue;
                            found[n] = true;
                            if (--remaining == 0) return true;
                            break;
                        }
                    }
                    carried = Math.Min(overlap, length);
                    Buffer.BlockCopy(buffer, length - carried, buffer, 0, carried);
                }
            }
            return false;
        }
    }
}
'@
}

function Get-NativeBuild {
    param([Parameter(Mandatory=$true)][string]$BuildDirectory)
    $directory = Get-Item -LiteralPath $BuildDirectory -ErrorAction Stop
    if (!$directory.PSIsContainer -or $directory.PSProvider.Name -ne 'FileSystem') {
        throw 'ビルド先のフォルダーを選んでください。'
    }
    $root = $directory.FullName
    foreach ($relative in @('pcbnew/pcbnew.exe', 'pcbnew/_pcbnew.dll', 'vcpkg_installed/x64-windows/tools/python3/python.exe')) {
        if (!(Test-Path -LiteralPath (Join-Path $root $relative) -PathType Leaf)) {
            throw "ビルド済みの必要ファイルがありません: $relative`nネイティブ版のビルド先フォルダーを選んでください。"
        }
    }

    # The canvas UI belongs to KiCad's PCB binary. Depending on build layout it
    # can be a DLL or a KIFACE; a Python binding DLL alone does not identify it.
    Initialize-NativeMarkerScanner
    $markers = [string[]]@(
        '数値・計算式 → Enter確定 / Esc取消',
        '半径 (mm) · 中心固定',
        '寸法から基板外形を変更'
    )
    $readError = $false
    foreach ($candidate in (Get-ChildItem -LiteralPath (Join-Path $root 'pcbnew') -File -ErrorAction Stop)) {
        if ($candidate.Extension -notin @('.dll', '.kiface')) { continue }
        try {
            if ([SmartBoardDimensionSetup.BinaryMarkers]::ContainsAll($candidate.FullName, $markers)) {
                return $root
            }
        } catch [System.IO.IOException] { $readError = $true }
          catch [System.UnauthorizedAccessException] { $readError = $true }
    }
    if ($readError) {
        throw '本体ファイルを読み取れませんでした。PCBエディタを閉じて、読み取り可能なビルド先を選び直してください。'
    }
    throw '寸法を数字から編集する機能が見つかりません。通常版やパッチ適用前のビルドでは登録できません。ネイティブ版のパッチを適用してビルドしたフォルダーを選んでください。'
}
