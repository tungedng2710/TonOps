import {Component, inject, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {MatButtonModule} from '@angular/material/button';
import {finalize} from 'rxjs/operators';
import {ApiProjectsService} from '~/business-logic/api-services/projects.service';
import {Project} from '~/business-logic/model/projects/project';
import {DialogTemplateComponent} from '@common/shared/ui-components/overlay/dialog-template/dialog-template.component';

@Component({
  selector: 'sm-owned-project-delete-dialog',
  imports: [FormsModule, MatButtonModule, DialogTemplateComponent],
  template: `
    <sm-dialog-template iconClass="al-ico-trash" header="Delete Project" [displayX]="false">
      <p>Delete "{{data.name.split('/').pop()}}" and all its tasks, models, reports, pipelines, datasets, and artifacts?</p>
      <p>Enter your password to confirm. This cannot be undone.</p>
      <form (ngSubmit)="delete()">
        <label for="project-delete-password">Password</label>
        <input id="project-delete-password" name="password" type="password" autocomplete="current-password"
               [(ngModel)]="password" [disabled]="deleting()" required class="form-control" />
        @if (error()) {
          <p class="error" role="alert">{{error()}}</p>
        }
        <div class="buttons">
          <button mat-flat-button color="warn" type="submit" [disabled]="!password || deleting()">
            {{deleting() ? 'DELETING...' : 'DELETE'}}
          </button>
          <button mat-stroked-button type="button" (click)="dialogRef.close(false)" [disabled]="deleting()">CANCEL</button>
        </div>
      </form>
    </sm-dialog-template>
  `,
  styles: [`
    input { width: 100%; margin-top: 6px; }
    .error { color: var(--color-error); margin-top: 12px; }
    .buttons { display: flex; justify-content: center; gap: 16px; margin-top: 32px; }
  `]
})
export class OwnedProjectDeleteDialogComponent {
  protected data = inject<Project>(MAT_DIALOG_DATA);
  protected dialogRef = inject(MatDialogRef<OwnedProjectDeleteDialogComponent>);
  private projectsApi = inject(ApiProjectsService);
  protected password = '';
  protected deleting = signal(false);
  protected error = signal('');

  protected delete() {
    if (!this.password || this.deleting()) {
      return;
    }
    this.error.set('');
    this.deleting.set(true);
    this.projectsApi.projectsDelete({
      project: this.data.id,
      password: this.password,
      force: true,
      delete_contents: true,
      delete_external_artifacts: true
    }).pipe(finalize(() => {
      this.password = '';
      this.deleting.set(false);
    })).subscribe({
      next: () => this.dialogRef.close(true),
      error: error => this.error.set(error.status === 401 && error.error?.meta?.result_subcode === 22 ?
        'Incorrect password.' : 'Project deletion failed. Please try again.')
    });
  }
}
