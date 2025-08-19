#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

console.log('🔧 Cleaning build filenames...');

const buildDir = path.join(__dirname, '..', 'build');
const staticDir = path.join(buildDir, 'static');

// Function to rename files and update references
function cleanFilenames() {
  try {
    // Clean JS files
    const jsDir = path.join(staticDir, 'js');
    const jsFiles = fs.readdirSync(jsDir);
    let mainJsFile = jsFiles.find(file => file.startsWith('main.') && file.endsWith('.js'));
    
    if (mainJsFile && mainJsFile !== 'main.js') {
      fs.renameSync(
        path.join(jsDir, mainJsFile),
        path.join(jsDir, 'main.js')
      );
      console.log(`✅ Renamed ${mainJsFile} → main.js`);
    }

    // Clean CSS files  
    const cssDir = path.join(staticDir, 'css');
    const cssFiles = fs.readdirSync(cssDir);
    let mainCssFile = cssFiles.find(file => file.startsWith('main.') && file.endsWith('.css'));
    
    if (mainCssFile && mainCssFile !== 'main.css') {
      fs.renameSync(
        path.join(cssDir, mainCssFile),
        path.join(cssDir, 'main.css')
      );
      console.log(`✅ Renamed ${mainCssFile} → main.css`);
    }

    // Update index.html to reference clean filenames
    const indexPath = path.join(buildDir, 'index.html');
    let indexContent = fs.readFileSync(indexPath, 'utf8');
    
    // Replace hashed filenames with clean ones
    indexContent = indexContent.replace(/\/argumentSettler\/static\/js\/main\.[^"]+\.js/g, '/argumentSettler/static/js/main.js');
    indexContent = indexContent.replace(/\/argumentSettler\/static\/css\/main\.[^"]+\.css/g, '/argumentSettler/static/css/main.css');
    
    fs.writeFileSync(indexPath, indexContent);
    console.log('✅ Updated index.html with clean filenames');

    // Update asset-manifest.json
    const manifestPath = path.join(buildDir, 'asset-manifest.json');
    if (fs.existsSync(manifestPath)) {
      let manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
      manifest.files['main.css'] = '/argumentSettler/static/css/main.css';
      manifest.files['main.js'] = '/argumentSettler/static/js/main.js';
      manifest.entrypoints = ['static/css/main.css', 'static/js/main.js'];
      fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
      console.log('✅ Updated asset-manifest.json with clean filenames');
    }

    console.log('🎉 Build cleanup complete!');

  } catch (error) {
    console.error('❌ Error cleaning filenames:', error.message);
    process.exit(1);
  }
}

cleanFilenames();