# SPDX-License-Identifier: MIT
# Use the Unicode shell interface; WScript.Shell.Save can depend on the system code page.
function Initialize-UnicodeShortcut {
    if ('SmartBoardDimensionSetup.Shortcuts' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
namespace SmartBoardDimensionSetup {
    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    class ShellLink { }
    [ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IShellLinkW {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count, IntPtr findData, uint flags);
        void GetIDList(out IntPtr list);
        void SetIDList(IntPtr list);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder text, int count);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string text);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string path);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder args, int count);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string args);
        void GetHotkey(out short hotkey);
        void SetHotkey(short hotkey);
        void GetShowCmd(out int command);
        void SetShowCmd(int command);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int count, out int index);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
        void Resolve(IntPtr window, uint flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
    }
    public static class Shortcuts {
        public static void Save(string file, string target, string args, string working, string icon) {
            object obj = new ShellLink();
            try {
                IShellLinkW link = (IShellLinkW)obj;
                link.SetPath(target); link.SetArguments(args); link.SetWorkingDirectory(working);
                link.SetDescription("Smart Board Dimension native build"); link.SetIconLocation(icon, 0);
                ((IPersistFile)obj).Save(file, true);
            } finally { Marshal.FinalReleaseComObject(obj); }
        }
        public static string Arguments(string file) {
            object obj = new ShellLink();
            try {
                ((IPersistFile)obj).Load(file, 0);
                StringBuilder args = new StringBuilder(32768);
                ((IShellLinkW)obj).GetArguments(args, args.Capacity);
                return args.ToString();
            } finally { Marshal.FinalReleaseComObject(obj); }
        }
    }
}
'@
}
