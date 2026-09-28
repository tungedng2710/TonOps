import {Project} from '~/business-logic/model/projects/project';

export function isProjectOwner(project: Project, userId: string): boolean {
  const owner = project?.user as string | {id?: string};
  return !!userId && (typeof owner === 'string' ? owner : owner?.id) === userId;
}
