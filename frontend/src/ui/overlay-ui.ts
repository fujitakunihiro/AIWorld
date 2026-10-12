const $ = (id: string) => document.getElementById(id)!;

/** Keep the world clear until the player asks for a panel. */
export class OverlayUI {
  onObserve: () => void = () => {};
  constructor() {
    $('toggle-menu').onclick = () => this.menu($('world-menu').hidden);
    $('close-menu').onclick = () => { this.menu(false); $('toggle-menu').focus(); };
    $('toggle-edit').onclick = () => this.edit($('edit-tools').hidden);
    $('close-edit').onclick = () => { this.edit(false); $('toggle-edit').focus(); };
    for (const id of ['residents', 'open-instructions', 'civilization', 'open-history', 'open-tasks', 'settings', 'help']) {
      $(id).addEventListener('click', () => this.close());
    }
    $('start-building').addEventListener('click', () => this.close());
    // Selecting a resident from the menu also frees the screen behind their dialog.
    $('resident-list').addEventListener('click', event => { if ((event.target as Element).closest('button')) this.close(); });
    $('toggle-map').addEventListener('click', () => { this.menu(false); this.edit(false); });
    document.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || document.querySelector('dialog[open]')) return;
      const target = !$('world-menu').hidden ? 'toggle-menu' : !$('edit-tools').hidden ? 'toggle-edit' : !$('map-card').hidden ? 'toggle-map' : undefined;
      this.close(); if (target) $(target).focus();
    });
  }
  private mapClose() { $('map-card').hidden = true; $('toggle-map').setAttribute('aria-pressed', 'false'); }
  menu(open: boolean) {
    $('world-menu').hidden = !open; $('toggle-menu').setAttribute('aria-expanded', String(open));
    if (open) { this.edit(false); this.mapClose(); $('close-menu').focus(); }
  }
  edit(open: boolean) {
    $('edit-tools').hidden = !open; $('toggle-edit').setAttribute('aria-expanded', String(open));
    if (open) { this.menu(false); this.mapClose(); $('close-edit').focus(); }
    else this.onObserve();
  }
  close() { this.menu(false); this.edit(false); this.mapClose(); }
}
