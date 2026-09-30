import {ChangeDetectionStrategy, Component, inject} from '@angular/core';
import {Router} from '@angular/router';
import {MatDialog, MatDialogRef} from '@angular/material/dialog';
import {Store} from '@ngrx/store';
import {Project} from '~/business-logic/model/projects/project';
import {selectRecentProjects} from '../../common-dashboard.reducer';
import {getRecentProjects} from '../../common-dashboard.actions';
import {ProjectDialogComponent} from '@common/shared/project-dialog/project-dialog.component';
import {resetSelectedProject, setSelectedProjectId} from '@common/core/actions/projects.actions';
import {isExample} from '@common/shared/utils/shared-utils';
import {CARDS_IN_ROW} from '../../common-dashboard.const';
import {ProjectCardComponent} from '@common/shared/ui-components/panel/project-card/project-card.component';
import {PlusCardComponent} from '@common/shared/ui-components/panel/plus-card/plus-card.component';
import {MatButton} from '@angular/material/button';
import {MatIcon} from '@angular/material/icon';

@Component({
  selector: 'sm-dashboard-projects',
  templateUrl: './dashboard-projects.component.html',
  styleUrls: ['./dashboard-projects.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ProjectCardComponent,
    PlusCardComponent,
    MatIcon,
    MatButton
  ]
})
export class DashboardProjectsComponent {
  private store = inject(Store);
  protected router = inject(Router);
  private matDialog = inject(MatDialog);
  public recentProjectsList$ = this.store.selectSignal(selectRecentProjects);
  private dialog: MatDialogRef<ProjectDialogComponent>;
  readonly cardsInRow = CARDS_IN_ROW;

  constructor() {
    this.store.dispatch(resetSelectedProject());
  }


  public projectCardClicked(project: Project) {
    if (project.own_tasks === 0 && project.sub_projects.length > 0) {
      this.router.navigateByUrl(`projects/${project.id}/projects`)
    } else {
      this.router.navigateByUrl(`projects/${project.id}`);
    }
    this.store.dispatch(setSelectedProjectId({projectId: project.id, example: isExample(project)}));
  }

  public openCreateProjectDialog() {
    this.dialog = this.matDialog.open(ProjectDialogComponent, {
      panelClass: 'dialog-md',
      data: {
        mode: 'create',
      }
    });
    this.dialog.afterClosed().subscribe(projectHasBeenCreated => {
      if (projectHasBeenCreated) {
        this.store.dispatch(getRecentProjects());
      }
    });
  }
}
