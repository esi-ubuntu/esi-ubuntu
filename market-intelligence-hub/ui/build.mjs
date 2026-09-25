import { rm, mkdir, cp } from 'node:fs/promises';
await rm('dist',{recursive:true,force:true}); await mkdir('dist',{recursive:true}); await cp('index.html','dist/index.html'); await cp('src','dist/src',{recursive:true}); try{await cp('public','dist',{recursive:true});}catch{}
console.log('static UI build complete');
