import {ChangeDetectionStrategy, Component, DestroyRef, inject, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {Router, RouterLink, ActivatedRoute} from '@angular/router';
import {Store} from '@ngrx/store';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {PublicProfile, ProfileProject} from '~/features/settings/iam/iam.models';
import {selectCurrentUser} from '@common/core/reducers/users-reducer';
import {ApiReportsService} from '~/business-logic/api-services/reports.service';
import {IReport} from '@common/reports/reports.consts';
import {ReportCardComponent} from '@common/reports/report-card/report-card.component';
import {IReportsCreateRequest, ReportDialogComponent} from '@common/reports/report-dialog/report-dialog.component';
import {createReport} from '@common/reports/reports.actions';
import {excludedKey} from '@common/shared/utils/tableParamEncode';
import {MatDialog} from '@angular/material/dialog';
import {MatButton} from '@angular/material/button';
import {MatIcon} from '@angular/material/icon';

@Component({
  selector: 'sm-profiles',
  standalone: true,
  imports: [FormsModule, RouterLink, ReportCardComponent, MatButton, MatIcon],
  templateUrl: './profiles.component.html',
  styleUrl: './profiles.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class ProfilesComponent {
  private iam = inject(ApiIamService);
  private route = inject(ActivatedRoute);
  private store = inject(Store);
  private reportsApi = inject(ApiReportsService);
  private router = inject(Router);
  private dialog = inject(MatDialog);
  private destroyRef = inject(DestroyRef);
  currentUser = this.store.selectSignal(selectCurrentUser);
  search = '';
  people = signal<PublicProfile[]>([]);
  profile = signal<PublicProfile | null>(null);
  projects = signal<ProfileProject[]>([]);
  reports = signal<IReport[]>([]);
  reportsLoading = signal(false);
  reportsError = signal('');
  hasMoreReports = signal(false);
  private reportsPage = -1;
  private readonly reportsPageSize = 6;
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

  loadReports() {
    const person = this.profile();
    if (!person || this.reportsLoading()) return;
    const request = this.requestId;
    const page = this.reportsPage + 1;
    this.reportsLoading.set(true);
    this.reportsError.set('');
    this.reportsApi.reportsGetAllEx({
      user: [person.id],
      page,
      page_size: this.reportsPageSize,
      order_by: ['-last_update', 'id'],
      system_tags: [excludedKey, 'archived'],
      only_fields: ['id', 'name', 'comment', 'company', 'tags', 'project.id', 'project.name', 'user.id', 'user.name', 'status', 'last_update', 'system_tags']
    }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: result => {
        if (request !== this.requestId) return;
        const reports = (result.tasks ?? []) as IReport[];
        this.reports.update(current => [...current, ...reports]);
        this.reportsPage = page;
        this.hasMoreReports.set(reports.length === this.reportsPageSize);
        this.reportsLoading.set(false);
      },
      error: () => {
        if (request !== this.requestId) return;
        this.reportsError.set('Unable to load reports.');
        this.reportsLoading.set(false);
      }
    });
  }

  openCreateReport() {
    if (this.currentUser()?.id !== this.profile()?.id) return;
    this.dialog.open<ReportDialogComponent, unknown, IReportsCreateRequest>(ReportDialogComponent, {
      panelClass: 'dialog-md'
    }).afterClosed().pipe(takeUntilDestroyed(this.destroyRef)).subscribe(report => {
      if (report) this.store.dispatch(createReport({reportsCreateRequest: report}));
    });
  }

  openReport(report: IReport, event?: Event) {
    event?.preventDefault();
    this.router.navigate(['/reports', report.project?.id || '*', report.id]);
  }

  private loadProfile(id: string) {
    const request = ++this.requestId;
    this.profile.set(null);
    this.projects.set([]);
    this.reports.set([]);
    this.reportsPage = -1;
    this.reportsLoading.set(false);
    this.reportsError.set('');
    this.hasMoreReports.set(false);
    this.loading.set(true);
    this.error.set('');
    this.iam.getProfile(id).subscribe({
      next: result => {
        if (request !== this.requestId) return;
        this.profile.set(result.user);
        this.projects.set(result.projects ?? []);
        this.loading.set(false);
        this.loadReports();
      },
      error: () => {
        if (request !== this.requestId) return;
        this.error.set('This profile is unavailable.');
        this.loading.set(false);
      }
    });
  }
}
