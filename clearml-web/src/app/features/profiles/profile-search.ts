import {MatDialog} from '@angular/material/dialog';

export async function openProfileSearch(dialog: MatDialog) {
  const {ProfileSearchDialogComponent} = await import('./profile-search-dialog.component');
  dialog.open(ProfileSearchDialogComponent, {
    width: '560px',
    maxWidth: 'calc(100vw - 32px)',
    panelClass: 'profile-search-dialog',
    autoFocus: 'input',
    ariaLabel: 'Find a profile'
  });
}
