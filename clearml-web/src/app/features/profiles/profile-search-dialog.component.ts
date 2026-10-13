import {ChangeDetectionStrategy, Component, DestroyRef, inject, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {RouterLink} from '@angular/router';
import {MatDialogRef} from '@angular/material/dialog';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {PublicProfile} from '~/features/settings/iam/iam.models';

@Component({
  selector: 'sm-profile-search-dialog',
  imports: [FormsModule, RouterLink],
  templateUrl: './profile-search-dialog.component.html',
  styleUrl: './profile-search-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ProfileSearchDialogComponent {
  private iam = inject(ApiIamService);
  private destroyRef = inject(DestroyRef);
  protected dialogRef = inject(MatDialogRef<ProfileSearchDialogComponent>);
  protected search = '';
  protected people = signal<PublicProfile[]>([]);
  protected loading = signal(false);
  protected searched = signal(false);
  protected error = signal(false);
  protected page = signal(0);
  protected total = signal(0);
  protected totalPages = () => Math.max(1, Math.ceil(this.total() / 30));
  private requestId = 0;

  protected clearResults() {
    ++this.requestId;
    this.people.set([]);
    this.total.set(0);
    this.page.set(0);
    this.loading.set(false);
    this.searched.set(false);
    this.error.set(false);
  }

  protected findProfiles(page = 0) {
    const query = this.search.trim();
    if (query.length < 2 || this.loading()) return;
    const request = ++this.requestId;
    this.loading.set(true);
    this.error.set(false);
    this.iam.searchProfiles(query, page).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: result => {
        if (request !== this.requestId) return;
        this.people.set(result.users ?? []);
        this.total.set(result.total);
        this.page.set(page);
        this.searched.set(true);
        this.loading.set(false);
      },
      error: () => {
        if (request !== this.requestId) return;
        this.people.set([]);
        this.error.set(true);
        this.loading.set(false);
      }
    });
  }
}
