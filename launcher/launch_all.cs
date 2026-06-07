// Combined launcher: starts BOTH the playground and the robot renderer at once.
// This is what the "Twitch Playground.lnk" shortcut points to, so a single
// double-click brings up both windows.
//
// Rather than re-implement the uv launch logic, it just starts its two sibling
// launcher exes ("Twitch Playground.exe" and "Robot.exe") that make_shortcut.ps1
// builds next to it -- each owns its own launch concern.
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

class LaunchAll
{
    [STAThread]
    static int Main()
    {
        string exeDir = AppDomain.CurrentDomain.BaseDirectory;
        string[] siblings = { "Twitch Playground.exe", "Robot.exe" };

        var errors = new StringBuilder();
        foreach (string name in siblings)
        {
            string path = Path.Combine(exeDir, name);
            try
            {
                if (!File.Exists(path))
                {
                    errors.AppendLine("Missing: " + name + " (run make_shortcut.bat to build it)");
                    continue;
                }
                Process.Start(new ProcessStartInfo
                {
                    FileName = path,
                    WorkingDirectory = exeDir,
                    UseShellExecute = false,
                });
            }
            catch (Exception ex)
            {
                errors.AppendLine(name + ": " + ex.Message);
            }
        }

        if (errors.Length > 0)
        {
            MessageBox.Show(
                "Some components failed to launch:\n\n" + errors,
                "Twitch Playground", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        return 0;
    }
}
