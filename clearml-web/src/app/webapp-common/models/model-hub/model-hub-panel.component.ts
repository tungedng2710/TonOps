import {ChangeDetectionStrategy, Component, computed, effect, inject, input, signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {DatePipe} from '@angular/common';
import {RouterLink} from '@angular/router';
import {MatDialog} from '@angular/material/dialog';
import {MatButtonModule} from '@angular/material/button';
import {ApiModelsService} from '~/business-logic/api-services/models.service';
import {SelectedModel} from '../shared/models.model';
import {CopyClipboardComponent} from '@common/shared/ui-components/indicators/copy-clipboard/copy-clipboard.component';
import {RegisterModelDialogComponent} from './register-model-dialog.component';
import {exactModelName, modelParentId, modelVersion, shellQuote} from './model-hub.utils';
import {Store} from '@ngrx/store';
import {refreshModels} from '../actions/models-view.actions';
import {isReadOnly} from '@common/shared/utils/is-read-only';

@Component({
  selector: 'sm-model-hub-panel',
  templateUrl: './model-hub-panel.component.html',
  styleUrl: './model-hub-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, DatePipe, RouterLink, MatButtonModule, CopyClipboardComponent]
})
export class ModelHubPanelComponent {
  model = input.required<SelectedModel>();
  private api = inject(ApiModelsService);
  private dialog = inject(MatDialog);
  private store = inject(Store);
  protected tab = signal<'versions' | 'use' | 'serve'>('versions');
  protected versions = signal<SelectedModel[]>([]);
  protected loading = signal(false);
  protected error = signal(false);
  protected page = signal(0);
  protected hasMore = signal(false);
  protected reload = signal(0);
  protected increment = (value: number) => value + 1;
  protected versionLabel = modelVersion;
  protected parentId = computed(() => modelParentId(this.model().parent));
  protected readOnly = computed(() => isReadOnly(this.model()));
  protected serviceId = signal('');
  protected engine = signal('sklearn');
  protected endpointName = signal('my-model');
  protected endpointUrl = signal('');
  protected payload = signal('{}');
  protected payloadValid = computed(() => {
    try { JSON.parse(this.payload()); return true; } catch { return false; }
  });
  protected validUrl = computed(() => /^https?:\/\/[^\s]+$/.test(this.endpointUrl().trim()));
  protected useCode = computed(() => `from clearml import InputModel

model = InputModel(model_id=${JSON.stringify(this.model().id)})
weights_path = model.get_local_copy()
print(weights_path)
# Load weights_path using your model's framework and architecture.`);
  protected deployCode = computed(() => `# Requires an existing ClearML Serving service and running inference containers.
# Install clearml-serving in your configured environment.
# Supply your model's preprocess.py (input parsing, loading and prediction).
clearml-serving --id ${shellQuote(this.serviceId().trim() || '<service-id>')} model add \\
  --engine ${shellQuote(this.engine())} \\
  --endpoint ${shellQuote(this.endpointName().trim() || 'my-model')} \\
  --model-id ${shellQuote(this.model().id)} \\
  --preprocess 'preprocess.py'${this.engine() === 'triton' ? '\n# Triton additionally requires model input/output names, shapes and types.\n# Add those flags from your model configuration before running.' : ''}`);
  protected curlCode = computed(() => `curl --request POST ${shellQuote(this.endpointUrl().trim())} \\
  --header 'Content-Type: application/json' \\
  --data ${shellQuote(this.payload())}`);
  protected pythonCode = computed(() => `import json
import requests

response = requests.post(
    ${JSON.stringify(this.endpointUrl().trim())},
    json=json.loads(${JSON.stringify(this.payload())}),
    timeout=30,
)
response.raise_for_status()
print(response.json())`);

  constructor() {
    effect(onCleanup => {
      const model = this.model();
      const page = this.page();
      this.reload();
      if (!model?.id) return;
      this.loading.set(true);
      this.error.set(false);
      const subscription = this.api.modelsGetAllEx({name: exactModelName(model.name),
        project: model.project?.id ? [model.project.id] : undefined,
        order_by: ['-created', 'id'], page, page_size: 20,
        only_fields: ['id', 'name', 'tags', 'ready', 'created', 'project', 'parent', 'system_tags']
      }).subscribe({next: response => {
        const versions = response.models || [];
        this.versions.set(page ? [...this.versions(), ...versions] : versions);
        this.hasMore.set(versions.length === 20);
        this.loading.set(false);
      }, error: () => { this.error.set(true); this.loading.set(false); }});
      onCleanup(() => subscription.unsubscribe());
    });
    effect(() => {
      if (!this.model()?.id) return;
      this.page.set(0);
      this.versions.set([]);
      this.serviceId.set('');
      const framework = this.model().framework?.toLowerCase() || '';
      this.engine.set(/torch|tensorflow|onnx|keras/.test(framework) ? 'triton'
        : /xgboost/.test(framework) ? 'xgboost' : /lightgbm/.test(framework) ? 'lightgbm'
          : /scikit|sklearn/.test(framework) ? 'sklearn' : 'custom');
      this.endpointUrl.set('');
      this.payload.set('{}');
    });
  }

  protected addVersion() {
    const model = this.model();
    this.dialog.open(RegisterModelDialogComponent, {width: '680px', maxWidth: '95vw',
      data: {project: model.project, parent: model}}).afterClosed().subscribe(result => {
      if (result) {
        this.store.dispatch(refreshModels({hideLoader: false, autoRefresh: false}));
        this.page.set(0);
        this.reload.update(value => value + 1);
      }
    });
  }
}
