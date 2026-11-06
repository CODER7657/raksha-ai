import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { assertBuildEnv } from './scripts/check-build-env.mjs'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // loadEnv merges .env files with process.env, which is where Vercel and CI
  // put their variables. Checked here rather than in `prebuild` so that
  // `vercel build` (which calls vite directly) is covered too. The env dir is
  // this file's directory, which is Vite's default root, not the shell's cwd.
  const envDir = fileURLToPath(new URL('.', import.meta.url))
  assertBuildEnv(loadEnv(mode, envDir, 'VITE_'))

  return {
    plugins: [react(), tailwindcss()],
  }
})
