// Upload through the official SDK so PicGo handles authentication and multipart uploads.
const { mkdtemp, writeFile, rm } = require('node:fs/promises');
const { tmpdir } = require('node:os');
const { join, dirname, resolve } = require('node:path');
const { PicGo } = require('picgo');

async function uploadImages(paths, token) {
  if (!token) {
    throw new Error('Configure PICGO_CLOUD_TOKEN before uploading images');
  }
  if (!Array.isArray(paths) || paths.length === 0 ||
      paths.some(path => typeof path !== 'string' || path.length === 0)) {
    throw new Error('Expected a non-empty array of image paths');
  }

  const directory = await mkdtemp(join(tmpdir(), 'blog-picgo-'));
  try {
    const configPath = join(directory, 'config.json');
    await writeFile(configPath, JSON.stringify({
      picBed: { uploader: 'picgo-cloud', current: 'picgo-cloud' },
      settings: { picgoCloud: { token } },
      picgoPlugins: {},
      silent: true,
    }), { mode: 0o600 });
    const picgo = new PicGo(configPath);
    let failure;
    picgo.on('failed', error => { failure = error; });
    const urls = [];
    for (const path of paths) {
      failure = undefined;
      const output = await picgo.upload([path], { uploader: 'picgo-cloud' });
      if (failure) throw failure;
      if (!Array.isArray(output) || output.length !== 1) {
        throw new Error('PicGo Cloud did not return an uploaded image');
      }
      const url = output[0].imgUrl;
      if (typeof url !== 'string' || !url.startsWith('https://') || /\s/.test(url)) {
        throw new Error('PicGo Cloud did not return a public HTTPS image URL');
      }
      urls.push(url);
    }
    return urls;
  } finally {
    if (dirname(resolve(directory)) === resolve(tmpdir())) {
      await rm(directory, { recursive: true, force: true });
    }
  }
}

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const paths = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const urls = await uploadImages(paths, (process.env.PICGO_CLOUD_TOKEN || '').trim());
  process.stdout.write(JSON.stringify(urls));
}

if (require.main === module) {
  main().catch(error => {
    const token = (process.env.PICGO_CLOUD_TOKEN || '').trim();
    let message = error instanceof Error ? error.message : 'Upload failed';
    if (token) message = message.split(token).join('[REDACTED]');
    message = message.replace(/https?:\/\/\S+/g, '[URL]');
    process.stderr.write(`PicGo Cloud: ${message}\n`);
    process.exitCode = 1;
  });
}
