import { defineConfig, presetUno, presetTypography } from 'unocss';

export default defineConfig({
	presets: [presetUno(), presetTypography()],
	content: {
		filesystem: ['src/**/*.{svelte,js,ts}', 'src/**/*.stories.{js,ts,svelte}', 'src/**/*.mdx']
	}
});
