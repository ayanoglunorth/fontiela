<div align="center">
  <img src="fontiela.svg" alt="Fontiela logo" width="80" height="80">

  # Fontiela

  **See how your fonts look on screen before you commit to a title card.**

  [Get started](#get-started) · [How it works](#how-it-works) · [Privacy](#privacy-and-font-licenses)
</div>

Fontiela is a local font catalog for Windows. It gathers fonts installed for your user account and lets you try them in cinematic title cards. A separate collection of type treatments gives you a starting point for studio names, film titles, credits, and subtitles.

## Get started

You need Windows 10 or 11, Python 3.10 or newer, and Google Chrome or Microsoft Edge. Fontiela uses the Python standard library; there are no packages to install.

1. Download the repository and extract it to a folder.
2. Double-click `fontiela.cmd`. You can also run `python app.py` from a terminal.
3. Fontiela opens in your browser at `127.0.0.1`. The local server stays running while its Python process is open.

If Windows cannot find Python, install it and make sure `pythonw.exe` is on your `PATH`. If the browser does not open, check that Chrome or Edge is installed in its usual location.

## Make it yours

The **Fontlarım** catalog reads the fonts installed for your Windows user account. Search by family, style, or filename, choose a face on each card, and use the weight slider when a variable font provides one. After installing another font, select **Yeniden tara** to update the catalog. The interface is currently in Turkish; the catalog labels appear as Windows reports them.

The four preview fields control the studio name, film title, credit name, and subtitle separately. Changes update the individual cards, prepared combinations, and film-title comparison where applicable. Fontiela saves those fields in your browser's local storage. Use **Varsayılana dön** beside any field to restore its sample text.

The curated collection includes a Turkish character check and type settings you can carry into Premiere Pro. The Premiere guide is an example workflow; menu names may differ across versions.

## How it works

Fontiela reads the current user's Windows font registry entries and font folder. A small Python server exposes the catalog and serves only fonts inside that user font folder to the page on `127.0.0.1`. It does not scan fonts installed for every user on the machine. It accepts `.ttf`, `.otf`, and `.ttc` files; unreadable files and files larger than 32 MB are skipped.

The server tries ports `8765` through `8775` and opens the first available one. Closing the browser tab does not stop the server. End the Python process when you are done.

## Privacy and font licenses

Your installed font files stay on your computer. Fontiela does not upload them. The curated previews load stylesheets and font files from Google Fonts, so that part of the page makes external requests and needs an internet connection. Its download links open Google Fonts.

Fontiela's MIT license covers this project's code. Fonts you have installed, and fonts obtained through Google Fonts, have their own licenses. Check the license of each font before using it in published work.

## Development

Run the Python checks with:

```powershell
python -m unittest -v test_app.py
```

The application has no third-party Python dependencies. The interface lives in `index.html`; the local server and font scanner live in `app.py`.

## License

[MIT](LICENSE)
