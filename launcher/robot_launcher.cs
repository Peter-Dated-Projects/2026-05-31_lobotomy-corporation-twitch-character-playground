// Tiny launcher for the robot face renderer.
// Runs `uv run --group robot robot` from the project directory. Compiled to an
// .exe so it can carry an embedded icon (a raw .bat cannot). The pygame window
// keeps its own caption/icon -- this launcher does not touch it.
//
// Mirrors launcher.cs (the playground launcher); the only differences are the
// uv arguments and the error-dialog title.
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

class RobotLauncher
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
            Arguments = "run --group robot robot",
            WorkingDirectory = projectDir,
            UseShellExecute = false,
            CreateNoWindow = true, // suppress the child uv/python console window
        };

        try
        {
            Process.Start(psi);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "Failed to launch the robot renderer:\n\n" + ex.Message,
                "Robot Renderer", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
