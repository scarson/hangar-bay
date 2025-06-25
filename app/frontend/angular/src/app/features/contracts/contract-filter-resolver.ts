import { ResolveFn } from '@angular/router';

export const contractFilterResolver: ResolveFn<boolean> = (route, state) => {
  return true;
};
