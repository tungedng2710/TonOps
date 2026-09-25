import {copyFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const source = fileURLToPath(new URL('../../brand_assets/background.png', import.meta.url));
const destination = fileURLToPath(new URL('../src/assets/login-background.png', import.meta.url));

copyFileSync(source, destination);
