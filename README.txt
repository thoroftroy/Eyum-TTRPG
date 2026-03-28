Eyum handbook site template

What this does:
- Builds a very simple GitHub Pages site from every .md file in the repo.
- Keeps folder structure in the left sidebar.
- Renders markdown in the main pane.
- Supports Obsidian-style [[Wiki Links]].
- Lets users change text color and background color in the top-right corner.
- Defaults to white text on black background.

How to use it:
1. Copy these files into the root of your handbook repo.
2. In GitHub repo settings:
   - Open Pages
   - Set Source to GitHub Actions
3. Push to main.
4. After that, every push rebuilds the site automatically.
5. You only edit your markdown files. No more site code changes should be needed unless you want new features.

Important limitation:
GitHub Pages cannot automatically browse your repository folders from browser-side JavaScript alone. That is why this template includes a GitHub Action and a tiny build script that generates manifest.json on every push.

Folders in this template:
- site/index.html
- site/styles.css
- site/app.js
- scripts/build.mjs
- .github/workflows/deploy-pages.yml
- package.json

What the build script does:
- Finds every .md file in the repo except ignored folders like .git, .github, node_modules, site, and dist.
- Copies them into dist/content/
- Builds dist/manifest.json for the file tree and default page.
- GitHub Pages serves dist/
