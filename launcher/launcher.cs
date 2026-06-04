// Tiny launcher for the Twitch character playground.
// Runs `uv run playground` from the project directory. Compiled to an .exe so
// it can carry an embedded icon (a raw .bat cannot). The pygame window keeps
// its own (default pygame) icon -- this launcher does not touch it.
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

class Launcher
{
    [STAThread]
    static int Main()
    {
        // The project root is the parent of the folder this exe lives in.
        string exeDir = AppDomain.CurrentDomain.BaseDirectory;
        string projectDir = Directory.GetParent(exeDir.TrimEnd('\\')).FullName;

        string uv = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            ".local", "bin", "uv.exe");
        if (!File.Exists(uv)) uv = "uv"; // fall back to PATH

        var psi = new ProcessStartInfo
        {
            FileName = uv,
            Arguments = "run playground",
            WorkingDirectory = projectDir,
            UseShellExecute = false,
        };

        try
        {
            Process.Start(psi);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "Failed to launch the playground:\n\n" + ex.Message,
                "Twitch Playground", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
