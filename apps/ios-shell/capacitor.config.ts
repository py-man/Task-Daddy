import type { CapacitorConfig } from "@capacitor/cli";

const serverUrl = process.env.IOS_SHELL_SERVER_URL || "http://localhost:3000";
const useLiveServer = process.env.IOS_SHELL_LIVE_SERVER === "1";

const config: CapacitorConfig = {
  appId: "com.neonlanes.app",
  appName: "Task-Daddy",
  webDir: "www",
  server: useLiveServer
    ? {
        url: serverUrl,
        cleartext: true
      }
    : undefined
};

export default config;
