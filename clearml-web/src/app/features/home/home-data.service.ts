import {inject, Injectable} from '@angular/core';
import {EMPTY, expand, forkJoin, map, Observable, of, reduce, switchMap} from 'rxjs';
import {ApiProjectsService} from '~/business-logic/api-services/projects.service';
import {ApiTasksService} from '~/business-logic/api-services/tasks.service';
import {Project} from '~/business-logic/model/projects/project';
import {IRecentTask} from '@common/dashboard/common-dashboard.reducer';
import {ProjectsGetAllExRequest} from '~/business-logic/model/projects/projectsGetAllExRequest';
import {excludedKey} from '@common/shared/utils/tableParamEncode';

export interface HomeSnapshot {
  projects: Project[];
  activities: IRecentTask[];
  running: IRecentTask[];
  updatedAt: Date;
}

// Match the scope of the totals, project cards, and activity feed.
const taskTypes = [excludedKey, 'report', excludedKey, 'annotation_manual', excludedKey, 'annotation', excludedKey, 'dataset_import'];
const taskTags = ['-archived', '-pipeline', '-report'];

@Injectable()
export class HomeDataService {
  private projectsApi = inject(ApiProjectsService);
  private tasksApi = inject(ApiTasksService);

  load(userId: string): Observable<HomeSnapshot> {
    const pageSize = 100;
    const getPage = (page: number) => this.projectsApi.projectsGetAllEx({
      active_users: [userId],
      include_stats: true,
      stats_for_state: ProjectsGetAllExRequest.StatsForStateEnum.Active,
      // Every project contributes its direct tasks once, even in nested projects.
      stats_with_children: false,
      include_stats_filter: {system_tags: taskTags, type: taskTypes},
      page,
      page_size: pageSize,
      order_by: ['-last_update', 'id'],
      only_fields: ['id', 'name', 'description', 'user.id', 'user.name', 'visibility', 'last_update']
    }).pipe(map(result => ({projects: result.projects ?? [], page})));

    return getPage(0).pipe(
      expand(result => result.projects.length === pageSize ? getPage(result.page + 1) : EMPTY),
      reduce((projects, result) => [...projects, ...result.projects], [] as Project[]),
      switchMap(projects => {
        if (!projects.length) return of({projects, activities: [], running: [], updatedAt: new Date()});
        const request = {
          user: [userId],
          project: projects.map(project => project.id),
          include_subprojects: false,
          page: 0,
          page_size: 8,
          type: taskTypes,
          system_tags: taskTags,
          order_by: ['-last_update', 'id'],
          only_fields: ['id', 'name', 'type', 'status', 'last_update', 'started', 'project.id', 'project.name']
        };
        return forkJoin({
          activities: this.tasksApi.tasksGetAllEx(request),
          running: this.tasksApi.tasksGetAllEx({...request, status: ['in_progress', 'queued']})
        }).pipe(map(result => ({
          projects,
          activities: (result.activities.tasks ?? []) as IRecentTask[],
          running: (result.running.tasks ?? []) as IRecentTask[],
          updatedAt: new Date()
        })));
      })
    );
  }
}
