import {version} from '../../../../../../version.json';

export interface CommercialContext {
  title?: string;
  subtitle?: string;
  background?: string;
  backgroundPosition?: string;
  list?: { icon: string; title: string; text: string }[];
}

export interface GettingStartedContext {
  install?: string;
  configure?: string;
  packageName?: string;
}

export interface Environment {
  production: boolean;
  apiBaseUrl: string;
  fileBaseUrl: string;
  displayedServerUrls?: {apiServer?: string; filesServer?: string};
  alternativeFilesBaseUrl?: string;
  headerPrefix: string;
  version: string;
  userKey: string;
  userSecret: string;
  companyID: string;
  loginNotice?: string;
  baseUrl?: string;
  autoLogin?: boolean;
  whiteLabelLogo?: boolean;
  whiteLabelLink?: {logo: string; tooltip: string; link: string};
  whiteLabelLoginTitle?: string;
  whiteLabelLoginSubtitle?: string;
  whiteLabelSlogan?: string;
  communityServer?: boolean;
  enterpriseServer?: boolean;
  gettingStartedContext?: GettingStartedContext;
  accountAdministration: boolean;
  communityContext?: CommercialContext;
  GTM_ID?: string;
  gtmResourcePath?: string;
  hideUpdateNotice?: boolean;
  updateCheck?: boolean;
  showSurvey?: boolean;
  plotlyURL?: string;
  docsLink?: string;
  useFilesProxy?: boolean;
  branding?: { faviconUrl?: string; logo?: string; logoSmall?: string };
  serverDownMessage?: string;
  appAwareness?: boolean;
  appAwarenessMenu?: boolean;
  baseHref?: string;
  billingServiceUrl?: string;
  loginPopup?: string;
  showMaskWithoutLabels?: boolean;
  autoLogoutInactiveDurationMinutes?: number;
  appcuesURL?: string;
}

export const BASE_ENV: Environment = {
  communityServer: false,
  enterpriseServer: true,
  accountAdministration: true,
  production: true,
  updateCheck: false,
  autoLogin: false,
  apiBaseUrl: null,
  fileBaseUrl: null,
  version,
  baseUrl: '',
  headerPrefix: 'X-Clearml',
  loginNotice: '',
  userKey: '',
  userSecret: '',
  companyID: '',
  whiteLabelLogo: null,
  whiteLabelLink: null,
  whiteLabelLoginTitle: null,
  whiteLabelLoginSubtitle: null,
  whiteLabelSlogan: null,
  plotlyURL: 'app/webapp-common/assets/plotly-2.35.0.min.js',
  docsLink: '/docs',
  useFilesProxy: true,
  branding: {logo: 'assets/logo-white.svg?v=7', logoSmall: 'assets/small-logo-white.svg?=2'},
  serverDownMessage: 'The TonOps server is currently unavailable.<BR>' +
    'Please try to reload this page in a little while.',
  showMaskWithoutLabels: true
};
