const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  modifyWebsite: (url, changes) =>
    ipcRenderer.invoke("modifyWebsite", url, changes),
});
