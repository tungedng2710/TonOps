import {ChangeDetectionStrategy, Component, DestroyRef, inject, signal} from '@angular/core';
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
import {headerActions} from '@common/core/actions/router.actions';
import {openProfileSearch as showProfileSearch} from './profile-search';

@Component({
  selector: 'sm-profiles',
  standalone: true,
  imports: [RouterLink, ReportCardComponent, MatButton, MatIcon],
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
  private requestId = 0;

  constructor() {
    this.store.dispatch(headerActions.reset());
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe(params => {
      this.loadProfile(params.get('username'));
    });
  }

  openProfileSearch() { void showProfileSearch(this.dialog); }

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

  private loadProfile(username: string) {
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
    this.iam.getProfile(username).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: result => {
        if (request !== this.requestId) return;
        if (username !== result.user.username) {
          void this.router.navigate(['/user', result.user.username], {replaceUrl: true});
          return;
        }
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
