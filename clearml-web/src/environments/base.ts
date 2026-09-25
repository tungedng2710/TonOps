import versionConf from '../version.json';
import {withDevtools} from '@angular-architects/ngrx-toolkit';

export interface CommunityContext {
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

export interface InterfaceCustomizations {
  clonePrefix: string;
}

export interface Environment {
  production: boolean;
  apiBaseUrl: string;
  fileBaseUrl: string;
  displayedServerUrls?: {apiServer?: string; filesServer?: string};
  productName: string;
  demo: boolean;
  headerPrefix: string;
  version: string;
  userKey: string;
  userSecret: string;
  companyID: string;
  loginNotice?: string;
  autoLogin?: boolean;
  whiteLabelLogo?: boolean;
  whiteLabelLink?: any;
  whiteLabelLoginTitle?: string;
  whiteLabelLoginSubtitle?: string;
  whiteLabelSlogan?: string;
  communityServer?: boolean;
  enterpriseServer?: boolean;
  accountAdministration: boolean;
  communityContext?: CommunityContext;
  GTM_ID?: string;
  hideUpdateNotice: boolean;
  showSurvey: boolean;
  plotlyURL: string;
  useFilesProxy: boolean;
  branding?: {faviconUrl?: string; logo?: string; logoSmall?: string};
  gettingStartedContext?: GettingStartedContext;
  serverDownMessage?: string;
  loginPopup?: string;
  baseHref?: string;
  loginFallback?: 'password-less' | 'error'; // defaults to 'password-less'
  displayTips: boolean;
  onlyPasswordLogin: boolean;
  blockUserScript?: boolean;
  forceTheme?: 'light' | 'dark';
  defaultTheme?: 'light' | 'dark';
  customStyle?: string;
  interfaceCustomization?: InterfaceCustomizations| undefined;
  storeDevToolsFeature: typeof withDevtools,
}

export const BASE_ENV = {
  production: true,
  apiBaseUrl: null,
  fileBaseUrl: null,
  productName: 'TonOps',
  demo: false,
  headerPrefix: 'X-Clearml',
  version: versionConf.version,
  userKey: 'EYVQ385RW7Y2QQUH88CZ7DWIQ1WUHP',
  userSecret: 'XhkH6a6ds9JBnM_MrahYyYdO-wS2bqFSm8gl-V0UZXH26Ydd6Eyi28TeBEoSr6Z3Bes',
  companyID: 'd1bd92a3b039400cbafc60a7a5b1e52b',
  loginNotice: '',
  autoLogin: false,
  whiteLabelLogo: null,
  whiteLabelLink: null,
  whiteLabelLoginTitle: null,
  whiteLabelLoginSubtitle: null,
  whiteLabelSlogan: null,
  storeDevToolsFeature: withDevtools,
  communityContext: {
    background: 'app/webapp-common/assets/icons/human-polygon.svg'
  },
  GTM_ID: null,
  hideUpdateNotice: false,
  showSurvey: false,
  accountAdministration: false,
  useFilesProxy: true,
  plotlyURL: 'app/webapp-common/assets/plotly-2.35.0.min.js',
  branding: {logo: 'assets/tonops-logo-white.svg?v=1', logoSmall: 'assets/tonops-icon-white.svg?v=1'},
  serverDownMessage: 'The TonOps server is currently unavailable.<BR>' +
    'Please try to reload this page in a little while.<BR>' +
    'If the problem persists, verify your network connection is working and check the TonOps server logs for possible errors',
  displayTips: true,
} as Environment;
