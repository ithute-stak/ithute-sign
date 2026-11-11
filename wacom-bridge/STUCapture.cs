using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Reflection;

namespace IthuteSignWacom
{
    /// <summary>
    /// Native Wacom STU device probe. Capture/display remain deliberately fail-closed
    /// until the vendor SDK integration and real tablet testing are completed.
    /// </summary>
    internal static class STUCapture
    {
        private const int NoDevice = 10;
        private const int SdkFailure = 11;
        private const int Unsupported = 12;
        private const int Unexpected = 13;

        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                if (args.Length == 1 && args[0] == "--probe")
                    return Probe();
                if (args.Length == 1 && (args[0] == "--welcome" || args[0] == "--thanks"))
                {
                    Console.Error.WriteLine("Tablet branding is not implemented; refusing to report success.");
                    return Unsupported;
                }
                if (args.Length == 1 && !args[0].StartsWith("--", StringComparison.Ordinal))
                {
                    // Never create a placeholder PNG: a successful capture must be genuine.
                    Console.Error.WriteLine("Real pen capture and confirmation are not yet implemented.");
                    return Unsupported;
                }
                Console.Error.WriteLine("Usage: STUCapture.exe --probe|--welcome|--thanks|<output.png>");
                return Unsupported;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("STU bridge failed: " + ex.Message);
                return Unexpected;
            }
        }

        private static int Probe()
        {
            object devices = null;
            object tablet = null;
            try
            {
                // Resolve the SDK's COM interop assembly at runtime. This keeps the
                // executable buildable without hard-coding a vendor SDK version.
                var assembly = Assembly.Load("Interop.wgssSTU");
                var devicesType = assembly.GetType("wgssSTU.UsbDevices", true);
                var tabletType = assembly.GetType("wgssSTU.Tablet", true);
                devices = Activator.CreateInstance(devicesType);
                int count = Convert.ToInt32(devicesType.InvokeMember(
                    "Count", BindingFlags.GetProperty, null, devices, null));
                if (count < 1)
                {
                    Console.Error.WriteLine("No Wacom STU device detected.");
                    return NoDevice;
                }
                var device = devicesType.InvokeMember("Item", BindingFlags.GetProperty,
                    null, devices, new object[] { 0 });
                tablet = Activator.CreateInstance(tabletType);
                // A successful enumeration alone is insufficient: connect to the
                // actual tablet before returning the connected exit code.
                tabletType.InvokeMember("usbConnect", BindingFlags.InvokeMethod,
                    null, tablet, new object[] { device, true });
                Console.WriteLine("Wacom STU device connected.");
                return 0;
            }
            catch (FileNotFoundException ex)
            {
                Console.Error.WriteLine("Wacom interop assembly missing: " + ex.Message);
                return SdkFailure;
            }
            catch (TypeLoadException ex)
            {
                Console.Error.WriteLine("Wacom SDK type unavailable: " + ex.Message);
                return SdkFailure;
            }
            catch (COMException ex)
            {
                Console.Error.WriteLine("Wacom USB/COM connection failed: " + ex.Message);
                return SdkFailure;
            }
            catch (TargetInvocationException ex)
            {
                Console.Error.WriteLine("Wacom SDK invocation failed: " +
                    (ex.InnerException == null ? ex.Message : ex.InnerException.Message));
                return SdkFailure;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Wacom probe failed: " + ex.Message);
                return SdkFailure;
            }
            finally
            {
                if (tablet != null)
                {
                    try
                    {
                        tablet.GetType().InvokeMember("disconnect", BindingFlags.InvokeMethod,
                            null, tablet, new object[0]);
                    }
                    catch (Exception) { /* Preserve original probe result. */ }
                    if (Marshal.IsComObject(tablet)) Marshal.FinalReleaseComObject(tablet);
                }
                if (devices != null && Marshal.IsComObject(devices))
                    Marshal.FinalReleaseComObject(devices);
            }
        }
    }
}
