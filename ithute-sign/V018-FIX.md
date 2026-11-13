# v0.18 fix

The Wacom bridge now sets connectedAt and starts the pen watchdog immediately after successful USB connection. This fixes CS0649 and enables the callback heartbeat. The Wacom pen-data callback remains unverified on hardware.
