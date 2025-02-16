document.getElementById("modify").addEventListener("click", async () => {
  const url = document.getElementById("url").value;
  const changes = document.getElementById("changes").value;
  const status = document.getElementById("status");

  if (!url || !changes) {
    status.innerText = "Please enter a URL and changes.";
    return;
  }

  status.innerText = "Processing...";

  const modifiedHTML = await window.api.modifyWebsite(url, changes);

  if (modifiedHTML.error) {
    status.innerText = "Error: Unable to modify website.";
  } else {
    const newWindow = window.open();
    newWindow.document.write(modifiedHTML);
    status.innerText = "Website modified!";
  }
});
