const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const axios = require("axios");

let mainWindow;

app.whenReady().then(() => {
  mainWindow = new BrowserWindow({
    width: 350,
    height: 600,
    alwaysOnTop: true,
    transparent: false,
    frame: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.loadFile("index.html");

  ipcMain.handle("modifyWebsite", async (event, url, changes) => {
    try {
      const response = await axios.post("http://127.0.0.1:8000/modify", {
        url,
        changes,
      });
      return response.data.html;
    } catch (error) {
      return { error: "Failed to modify website" };
    }
  });
});
