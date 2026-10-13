import {ChangeDetectionStrategy, Component, computed, inject, signal} from '@angular/core';
import {DatePipe, DecimalPipe} from '@angular/common';
import {RouterLink} from '@angular/router';
import {Store} from '@ngrx/store';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {catchError, combineLatest, distinctUntilChanged, filter, map, merge, of, Subject, switchMap, tap, timer} from 'rxjs';
import {selectActiveWorkspace, selectCurrentUser} from '@common/core/reducers/users-reducer';
import {headerActions} from '@common/core/actions/router.actions';
import {Project} from '~/business-logic/model/projects/project';
import {HomeDataService, HomeSnapshot} from './home-data.service';

@Component({
  selector: 'sm-home',
  imports: [RouterLink, DatePipe, DecimalPipe],
  providers: [HomeDataService],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class HomeComponent {
  private store = inject(Store);
  private data = inject(HomeDataService);
  private refreshRequested = new Subject<void>();
  protected user = this.store.selectSignal(selectCurrentUser);
  protected snapshot = signal<HomeSnapshot | null>(null);
  protected loading = signal(true);
  protected error = signal(false);
  protected now = signal(new Date());
  protected greeting = computed(() => {
    const hour = this.now().getHours();
    return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  });
  protected projects = computed(() => this.snapshot()?.projects ?? []);
  protected counts = computed(() => {
    const counts: Record<string, number> = {};
    for (const project of this.projects()) {
      for (const [status, count] of Object.entries(project.stats?.active?.status_count ?? {})) {
        counts[status] = (counts[status] ?? 0) + count;
      }
    }
    return counts;
  });
  protected totalTasks = computed(() => Object.values(this.counts()).reduce((total, count) => total + count, 0));
  protected runningCount = computed(() => this.counts()['in_progress'] ?? 0);
  protected queuedCount = computed(() => this.counts()['queued'] ?? 0);
  protected failedCount = computed(() => this.counts()['failed'] ?? 0);
  protected completedCount = computed(() => ['completed', 'published', 'closed'].reduce((total, status) => total + (this.counts()[status] ?? 0), 0));
  protected statuses = computed(() => [
    {label: 'Completed', count: this.completedCount(), color: '#22b991'},
    {label: 'Running', count: this.runningCount(), color: '#4584f5'},
    {label: 'Queued', count: this.queuedCount(), color: '#a38aee'},
    {label: 'Failed', count: this.failedCount(), color: '#ed7a87'},
    {label: 'Stopped', count: this.counts()['stopped'] ?? 0, color: '#e9b45f'},
    {label: 'Draft / other', count: this.totalTasks() - this.completedCount() - this.runningCount() - this.queuedCount() - this.failedCount() - (this.counts()['stopped'] ?? 0), color: '#c1cddb'}
  ]);
  protected donut = computed(() => {
    if (!this.totalTasks()) return '#edf2f8';
    let position = 0;
    const stops = this.statuses().filter(status => status.count > 0).map(status => {
      const start = position;
      position += status.count / this.totalTasks() * 100;
      return `${status.color} ${start}% ${position}%`;
    });
    return `conic-gradient(from -90deg, ${stops.join(', ')})`;
  });
  protected chartDescription = computed(() => this.statuses().map(status => `${status.label}: ${status.count}`).join(', '));
  protected completedPercent = computed(() => this.totalTasks() ? Math.round(this.completedCount() / this.totalTasks() * 100) : 0);
  protected visibleProjects = computed(() => this.projects().slice(0, 6));

  constructor() {
    this.store.dispatch(headerActions.reset());
    const identity = combineLatest([
      this.store.select(selectCurrentUser), this.store.select(selectActiveWorkspace)
    ]).pipe(
      filter(([user]) => !!user?.id),
      distinctUntilChanged(([user, workspace], [nextUser, nextWorkspace]) => user.id === nextUser.id && workspace?.id === nextWorkspace?.id),
      tap(() => this.snapshot.set(null))
    );
    identity.pipe(
      switchMap(([user]) => merge(timer(0, 60000).pipe(filter(() => !document.hidden)), this.refreshRequested).pipe(
        tap(() => { this.loading.set(true); this.error.set(false); }),
        switchMap(() => this.data.load(user.id).pipe(catchError(() => of(null))))
      )),
      takeUntilDestroyed()
    ).subscribe(snapshot => {
      if (snapshot) this.snapshot.set(snapshot);
      this.error.set(!snapshot);
      this.loading.set(false);
      this.now.set(new Date());
    });
  }

  protected refresh() { this.refreshRequested.next(); }
  protected projectTaskCount(project: Project) { return project.stats?.active?.total_tasks ?? 0; }
  protected projectRunning(project: Project) { return project.stats?.active?.status_count?.in_progress ?? 0; }
  protected ownerName(project: Project) {
    return typeof project.user === 'object' ? project.user.name || 'Unknown owner' : 'Unknown owner';
  }
  protected statusLabel(status: string) {
    return ({in_progress: 'Running', created: 'Draft', closed: 'Closed', published: 'Published', completed: 'Completed', failed: 'Failed', queued: 'Queued', stopped: 'Stopped', publishing: 'Publishing'})[status] ?? 'Unknown';
  }
  protected relativeTime(value: string | Date) {
    if (!value) return 'No update time';
    const elapsed = this.now().getTime() - new Date(value).getTime();
    if (!Number.isFinite(elapsed)) return 'No update time';
    const minutes = Math.max(0, Math.floor(elapsed / 60000));
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
    return `${Math.floor(minutes / 1440)}d ago`;
  }
}
