# Frontend – Consumer Loan Origination System

React + Vite + TypeScript application for agentic loan origination.

## Features

- **Authentication**: Cognito Hosted UI with PKCE flow
- **Application Intake**: Form-based loan application submission
- **Document Upload**: Drag/drop upload via S3 presigned URLs
- **Real-time Status**: Live polling of application processing status
- **Decision Review**: Structured decision display with artifact downloads
- **Role-based Access**: LoanOfficer and Operator roles with protected routes
- **Responsive Design**: Mobile-first, accessible UI components
- **Type Safety**: Full TypeScript coverage with shared schema alignment

## Technology Stack

- **React 19** with hooks
- **Vite 6** for fast builds
- **TypeScript** for type safety
- **React Router 7** for routing
- **React Query** (TanStack Query) for API state management
- **AWS Amplify** for Cognito authentication
- **React Hook Form** for form validation
- **Axios** for HTTP requests
- **Vitest** + Testing Library for testing

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client and configuration
│   │   └── client.ts     # Typed API client with interceptors
│   ├── components/       # React components
│   │   ├── ui/           # Shared UI components (Button, Input, Card, etc.)
│   │   ├── ApplicationForm.tsx
│   │   ├── DocumentUpload.tsx
│   │   ├── ApplicationStatus.tsx
│   │   ├── DecisionView.tsx
│   │   ├── Layout.tsx
│   │   ├── ProtectedRoute.tsx
│   │   └── ErrorBoundary.tsx
│   ├── contexts/         # React contexts
│   │   └── AuthContext.tsx
│   ├── hooks/            # Custom hooks
│   │   └── useApi.ts     # API hooks with React Query
│   ├── pages/            # Page components
│   │   ├── HomePage.tsx
│   │   ├── LoginPage.tsx
│   │   └── AdminPage.tsx
│   ├── styles/           # CSS styles
│   │   └── index.css     # Design system and component styles
│   ├── test/             # Test utilities
│   │   ├── setup.ts
│   │   └── utils.tsx
│   ├── types/            # TypeScript types
│   │   └── index.ts      # Canonical schema types
│   ├── config/           # Configuration
│   │   ├── api.ts
│   │   └── auth.ts
│   ├── App.tsx           # Root component
│   └── main.tsx          # Entry point
├── tests/                # Test files
│   ├── hooks/
│   └── components/
├── .env.example          # Environment variables template
├── vite.config.ts        # Vite configuration
├── vitest.config.ts      # Vitest configuration
├── tsconfig.json         # TypeScript configuration
└── package.json
```

## Getting Started

### Prerequisites

- Node.js 20+
- npm or yarn

### Installation

```bash
npm install
```

### Configuration

Copy `.env.example` to `.env.local` and populate:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_AWS_REGION=us-east-1
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_COGNITO_USER_POOL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_COGNITO_OAUTH_DOMAIN=your-domain.auth.us-east-1.amazoncognito.com
VITE_COGNITO_REDIRECT_SIGN_IN=http://localhost:5173
VITE_COGNITO_REDIRECT_SIGN_OUT=http://localhost:5173
```

### Development

Start the development server:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

### Building

Build for production:

```bash
npm run build
```

Preview production build:

```bash
npm run preview
```

## Testing

Run tests:

```bash
npm run test
```

Run tests in UI mode:

```bash
npm run test:ui
```

Run tests with coverage:

```bash
npm run test:coverage
```

## Code Quality

### Linting

```bash
npm run lint
npm run lint:fix
```

### Formatting

```bash
npm run format
npm run format:check
```

## Architecture

### Authentication Flow

1. User clicks "Sign In with Cognito"
2. Redirected to Cognito Hosted UI
3. After successful auth, redirected back with authorization code
4. Amplify exchanges code for tokens (PKCE)
5. Tokens stored in memory and refreshed automatically
6. Access token attached to API requests via interceptor

### API Integration

All API calls use custom React Query hooks:

- `useCreateApplication()` - Create new application
- `useUploadDocument()` - Upload documents via presigned URLs
- `useSubmitApplication()` - Submit for processing
- `useApplication()` - Get application details (with polling)
- `useDecision()` - Get decision results

### State Management

- **Authentication**: React Context (`AuthContext`)
- **API State**: React Query
- **Form State**: React Hook Form
- **Local UI State**: React hooks (`useState`, `useReducer`)

### Type Safety

TypeScript types in `src/types/index.ts` mirror the Python Pydantic schemas in `shared/schemas/`. This ensures frontend-backend contract alignment.

### Accessibility

- Semantic HTML
- ARIA attributes on interactive elements
- Keyboard navigation support
- Screen reader friendly
- Focus management
- Error announcements

### Responsive Design

- Mobile-first approach
- Breakpoints: 768px (tablet), 1024px (desktop)
- Flexible layouts with CSS Grid and Flexbox
- Touch-friendly interactive elements

## Design System

The app uses a consistent design system defined in `src/styles/index.css`:

- **Colors**: Primary, secondary, danger, success, warning
- **Spacing**: XS (0.25rem) to 2XL (3rem)
- **Typography**: System fonts, 5 size scales
- **Components**: Buttons, inputs, cards, badges, alerts
- **Shadows**: SM, MD, LG elevation levels

## Component Library

### UI Components

- `Button` - Primary, secondary, danger variants with loading states
- `Input` - Form input with label, error, and helper text
- `Card` - Content container with optional header
- `LoadingSpinner` - Loading indicator with size variants
- `EmptyState` - Empty data placeholder
- `ErrorMessage` - Error display with retry option

### Page Components

- `ApplicationForm` - Multi-field application intake
- `DocumentUpload` - Drag/drop document upload
- `ApplicationStatus` - Real-time status tracking
- `DecisionView` - Decision details and artifacts

## Deployment

The frontend can be deployed to:

- **S3 + CloudFront**: Static hosting with CDN
- **Amplify Hosting**: Managed CI/CD
- **Vercel/Netlify**: Alternative static hosting

Build output is in `dist/` directory.

## Troubleshooting

### Cognito Authentication Issues

- Verify redirect URIs match in Cognito app client settings
- Check CORS configuration on backend API
- Ensure OAuth domain is correct

### API Connection Issues

- Verify `VITE_API_BASE_URL` is correct
- Check backend is running
- Inspect network tab for CORS errors

### Build Errors

- Clear `node_modules` and reinstall: `rm -rf node_modules package-lock.json && npm install`
- Check TypeScript errors: `npx tsc --noEmit`

## Contributing

Follow the project's coding standards:

- TypeScript strict mode enabled
- ESLint + Prettier for code formatting
- All components must have tests
- Accessibility is required, not optional

## License

Internal enterprise project.
