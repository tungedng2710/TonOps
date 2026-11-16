import {SelectedModel} from '../shared/models.model';

export const modelVersion = (model: Pick<SelectedModel, 'tags' | 'id'>): string =>
  model.tags?.find(tag => tag.startsWith('version:'))?.slice(8) || model.id.slice(0, 8);

export const modelParentId = (parent: string | {id?: string}): string =>
  typeof parent === 'string' ? parent : parent?.id;

export const shellQuote = (value: string): string => `'${value.replace(/'/g, `'"'"'`)}'`;
export const exactModelName = (name: string): string => `^${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`;

export function uploadExample(project: string, name = 'my-model', parent?: string): string {
  return `from clearml import Task, OutputModel

# Run clearml-init first to configure this server and your storage credentials.
task = Task.init(project_name=${JSON.stringify(project)}, task_name="Register model")
model = OutputModel(task=task, name=${JSON.stringify(name)}, tags=["version:1.0.0"]${parent ? `,
                    base_model_id=${JSON.stringify(parent)}` : ''})
# Use your configured storage destination (S3, GS, Azure, or fileserver).
model.update_weights(weights_filename="/path/to/model.pt", auto_delete_file=False)
OutputModel.wait_for_uploads()
print(model.id)
# Publish after validation: model.publish()
task.close()`;
}
