import {ChangeDetectionStrategy, Component, inject, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {RouterLink, ActivatedRoute} from '@angular/router';
import {Store} from '@ngrx/store';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {PublicProfile, ProfileProject} from '~/features/settings/iam/iam.models';
import {selectCurrentUser} from '@common/core/reducers/users-reducer';

@Component({
  selector: 'sm-profiles',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './profiles.component.html',
  styleUrl: './profiles.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ProfilesComponent {
  private iam = inject(ApiIamService);
  private route = inject(ActivatedRoute);
  private store = inject(Store);
  currentUser = this.store.selectSignal(selectCurrentUser);
  search = '';
  people = signal<PublicProfile[]>([]);
  profile = signal<PublicProfile | null>(null);
  projects = signal<ProfileProject[]>([]);
  loading = signal(false);
  error = signal('');
  total = signal(0);
  page = signal(0);
  totalPages = () => Math.max(1, Math.ceil(this.total() / 30));
  private requestId = 0;

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe(params => {
      const id = params.get('userId');
      if (id) this.loadProfile(id);
      else this.findPeople(0);
    });
  }

  findPeople(page = 0) {
    const request = ++this.requestId;
    this.profile.set(null);
    this.loading.set(true);
    this.error.set('');
    this.iam.searchProfiles(this.search.trim(), page).subscribe({
      next: result => {
        if (request !== this.requestId) return;
        this.people.set(result.users ?? []);
        this.total.set(result.total);
        this.page.set(page);
        this.loading.set(false);
      },
      error: () => {
        if (request !== this.requestId) return;
        this.error.set('Unable to load people.');
        this.loading.set(false);
      }
    });
  }

  private loadProfile(id: string) {
    const request = ++this.requestId;
    this.profile.set(null);
    this.projects.set([]);
    this.loading.set(true);
    this.error.set('');
    this.iam.getProfile(id).subscribe({
      next: result => {
        if (request !== this.requestId) return;
        this.profile.set(result.user);
        this.projects.set(result.projects ?? []);
        this.loading.set(false);
      },
      error: () => {
        if (request !== this.requestId) return;
        this.error.set('This profile is unavailable.');
        this.loading.set(false);
      }
    });
  }
}
