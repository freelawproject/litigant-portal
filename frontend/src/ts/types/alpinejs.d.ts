/**
 * Module declaration for alpinejs package
 * AlpineJS doesn't provide official TypeScript types
 */

declare module 'alpinejs' {
  export interface AlpineInstance {
    data(name: string, callback: () => any): void
    start(): void
    plugin(plugin: any): void
  }

  const Alpine: AlpineInstance
  export default Alpine
}
