import {ChangeDetectionStrategy, Component, DestroyRef, inject, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {MAT_DIALOG_DATA, MatDialogModule, MatDialogRef} from '@angular/material/dialog';
import {MatButtonModule} from '@angular/material/button';
import {Subject, of} from 'rxjs';
import {catchError, map, switchMap} from 'rxjs/operators';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {ApiProjectsService} from '~/business-logic/api-services/projects.service';
import {SelectedModel} from '../shared/models.model';
import {ModelRegistryService} from './model-registry.service';
import {CopyClipboardComponent} from '@common/shared/ui-components/indicators/copy-clipboard/copy-clipboard.component';
import {PaginatedEntitySelectorComponent, baseEntity} from '@common/shared/components/paginated-entity-selector/paginated-entity-selector.component';
import {rootProjectsPageSize} from '@common/constants';
import {shellQuote, uploadExample} from './model-hub.utils';
import {v4 as uuid} from 'uuid';

export interface RegisterModelData {
  project?: {id: string; name: string};
  parent?: SelectedModel;
  api?: boolean;
}

@Component({
  selector: 'sm-register-model-dialog',
  templateUrl: './register-model-dialog.component.html',
  styleUrl: './register-model-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatDialogModule, MatButtonModule, CopyClipboardComponent, PaginatedEntitySelectorComponent]
})
export class RegisterModelDialogComponent {
  protected data = inject<RegisterModelData>(MAT_DIALOG_DATA);
  private ref = inject(MatDialogRef<RegisterModelDialogComponent>);
  private registry = inject(ModelRegistryService);
  private projectsApi = inject(ApiProjectsService);
  private destroyRef = inject(DestroyRef);
  protected tab = signal<'gui' | 'api'>(this.data.api ? 'api' : 'gui');
  protected source: 'file' | 'uri' = 'file';
  protected name = this.data.parent?.name || '';
  protected framework = this.data.parent?.framework || '';
  protected version = '';
  protected comment = '';
  protected project: baseEntity | string = this.data.project?.id === '*' ? null : this.data.project;
  protected projects = signal<baseEntity[]>([]);
  protected busy = signal(false);
  protected error = signal('');
  protected draftId = signal<string>(null);
  protected file: File;
  protected uri = '';
  private draftUri: string;
  private projectPage = 0;
  private searchProjects$ = new Subject<{search: string; more: boolean}>();
  protected readonly uploadAvailable = !!this.registry.uploadServer;

  constructor() {
    this.searchProjects$.pipe(
      switchMap(({search, more}) => {
        this.projectPage = more ? this.projectPage + 1 : 0;
        return this.projectsApi.projectsGetAllEx({name: search ? search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') : undefined,
          page: this.projectPage, page_size: rootProjectsPageSize, order_by: ['name'],
          only_fields: ['id', 'name'], system_tags: ['-archived', '-dataset', '-pipeline']}).pipe(
          map(response => ({projects: response.projects || [], more})),
          catchError(() => { this.error.set('Unable to load projects. Search again to retry.'); return of({projects: [], more: false}); })
        );
      }), takeUntilDestroyed()
    ).subscribe(({projects, more}) => this.projects.set(more ? [...this.projects(), ...projects] : projects));
    if (!this.uploadAvailable) this.source = 'uri';
  }

  protected searchProjects(search: string, more = false) {
    this.searchProjects$.next({search, more});
  }

  protected get projectId(): string {
    // The shared selector emits the project's full name, not its object.
    return typeof this.project === 'string'
      ? this.projects().find(project => project.name === this.project)?.id
      : this.project?.id;
  }

  protected get apiExample(): string {
    const project = typeof this.project === 'object' ? this.project?.name : this.project;
    return uploadExample(project || 'My project', this.name || 'my-model', this.data.parent?.id);
  }

  protected get restExample(): string {
    return `# Set CLEARML_API_URL and CLEARML_TOKEN for your configured environment.
# This registers an existing file; it does not upload the weights.
curl --request POST "$CLEARML_API_URL/models.create" \\
  --header "Authorization: Bearer $CLEARML_TOKEN" \\
  --header 'Content-Type: application/json' \\
  --data ${shellQuote(JSON.stringify({name: this.name.trim() || 'my-model',
      project: this.projectId || '<project-id>', uri: 's3://bucket/model.pt', ready: false,
      tags: [`version:${this.version.trim() || '1.0.0'}`], ...(this.data.parent && {parent: this.data.parent.id})}))}`;
  }

  protected chooseFile(event: Event) {
    this.file = (event.target as HTMLInputElement).files?.[0];
  }

  protected async submit() {
    if (this.busy()) return;
    this.error.set('');
    if (!this.name.trim() || !this.projectId || !this.version.trim() ||
        (this.source === 'file' ? !this.file?.size : !/^(https?|s3|gs|azure):\/\/\S+$/.test(this.uri.trim()))) {
      this.error.set('Enter a name, select an existing project, add a version, and choose a non-empty file or valid storage URI.');
      return;
    }
    this.busy.set(true);
    this.ref.disableClose = true;
    try {
      if (!this.draftId()) {
        this.draftUri = this.source === 'file'
          ? `${this.registry.uploadServer}/models/${uuid()}/${this.file.name.replace(/[^a-zA-Z0-9._-]/g, '_')}`
          : this.uri.trim();
        this.draftId.set(await this.registry.create({name: this.name.trim(), project: this.projectId,
          framework: this.framework.trim() || undefined, comment: this.comment.trim(), uri: this.draftUri,
          parent: this.data.parent?.id, ready: false,
          tags: [...(this.data.parent?.tags || []).filter(tag => !tag.startsWith('version:')), `version:${this.version.trim()}`]}));
      }
      if (this.source === 'file') await this.registry.upload(this.file, this.draftUri);
      this.ref.close({id: this.draftId(), project: this.projectId});
    } catch {
      if (!this.destroyRef.destroyed) this.error.set(this.draftId()
        ? `Draft ${this.draftId()} was registered, but the browser could not confirm the upload. The file may already be stored. Retry uses this same draft and file; closing keeps the draft.`
        : 'Registration failed. Check project write access and your connection. Refresh the registry before retrying if the request timed out.');
    } finally {
      if (!this.destroyRef.destroyed) this.busy.set(false);
      this.ref.disableClose = false;
    }
  }
}
