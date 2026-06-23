/**
 * Document upload component with drag/drop and progress tracking.
 * Uploads pay stub and bank statement via presigned S3 URLs.
 */

import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useUploadDocument } from '../hooks/useApi';
import { Button, Card, LoadingSpinner } from './ui';
import { DocumentType } from '../types';

interface UploadedFile {
  type: DocumentType;
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
}

const ACCEPTED_FILE_TYPES = ['application/pdf'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export function DocumentUpload() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const navigate = useNavigate();
  const { uploadDocument, isLoading } = useUploadDocument();

  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const validateFile = (file: File): string | null => {
    if (!ACCEPTED_FILE_TYPES.includes(file.type)) {
      return 'Only PDF files are accepted';
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File size must be less than ${MAX_FILE_SIZE / (1024 * 1024)}MB`;
    }
    return null;
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(Array.from(e.target.files));
    }
  };

  const handleFiles = (files: File[]) => {
    // For now, expect exactly 2 files: pay stub and bank statement
    if (files.length !== 2) {
      alert('Please upload exactly 2 documents: 1 pay stub and 1 bank statement');
      return;
    }

    const newFiles: UploadedFile[] = [];
    for (const file of files) {
      const error = validateFile(file);
      if (error) {
        alert(`${file.name}: ${error}`);
        continue;
      }

      // Simple heuristic: if filename contains "pay" or "stub", it's a pay stub
      const isPayStub = /pay|stub/i.test(file.name);
      const type = isPayStub ? DocumentType.PAYSTUB : DocumentType.BANK_STATEMENT;

      newFiles.push({
        type,
        file,
        status: 'pending',
      });
    }

    setUploadedFiles(newFiles);
  };

  const handleUpload = async () => {
    if (!applicationId || uploadedFiles.length === 0) return;

    for (let i = 0; i < uploadedFiles.length; i++) {
      const uploadedFile = uploadedFiles[i];
      
      setUploadedFiles((prev) =>
        prev.map((f, idx) => (idx === i ? { ...f, status: 'uploading' } : f))
      );

      try {
        await uploadDocument(applicationId, uploadedFile.type, uploadedFile.file);
        
        setUploadedFiles((prev) =>
          prev.map((f, idx) => (idx === i ? { ...f, status: 'success' } : f))
        );
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Upload failed';
        setUploadedFiles((prev) =>
          prev.map((f, idx) => (idx === i ? { ...f, status: 'error', error: errorMessage } : f))
        );
      }
    }
  };

  const allUploaded = uploadedFiles.length > 0 && uploadedFiles.every((f) => f.status === 'success');

  const handleContinue = () => {
    if (applicationId) {
      navigate(`/applications/${applicationId}/submit`);
    }
  };

  return (
    <Card title="Upload Documents">
      <div className="document-upload">
        <p className="document-upload__instructions">
          Please upload 2 documents:
        </p>
        <ul className="document-upload__requirements">
          <li>Pay stub (PDF)</li>
          <li>Bank statement (PDF)</li>
        </ul>

        <div
          className={`document-upload__dropzone ${dragActive ? 'document-upload__dropzone--active' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf"
            onChange={handleFileInput}
            className="document-upload__input"
            id="file-input"
          />
          <label htmlFor="file-input" className="document-upload__label">
            <p>Drag and drop files here, or click to select files</p>
            <p className="document-upload__hint">PDF files only, max 10MB each</p>
          </label>
        </div>

        {uploadedFiles.length > 0 && (
          <div className="document-upload__files">
            <h4>Selected Files:</h4>
            <ul className="document-upload__file-list">
              {uploadedFiles.map((uploadedFile, idx) => (
                <li key={idx} className="document-upload__file-item">
                  <div className="document-upload__file-info">
                    <span className="document-upload__file-name">{uploadedFile.file.name}</span>
                    <span className="document-upload__file-type">{uploadedFile.type}</span>
                  </div>
                  <div className="document-upload__file-status">
                    {uploadedFile.status === 'pending' && <span>Pending</span>}
                    {uploadedFile.status === 'uploading' && <LoadingSpinner size="sm" />}
                    {uploadedFile.status === 'success' && <span className="status-success">✓ Uploaded</span>}
                    {uploadedFile.status === 'error' && (
                      <span className="status-error">✗ {uploadedFile.error}</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="document-upload__actions">
          {!allUploaded && (
            <Button
              onClick={handleUpload}
              isLoading={isLoading}
              disabled={uploadedFiles.length === 0}
              fullWidth
            >
              Upload Documents
            </Button>
          )}
          {allUploaded && (
            <Button onClick={handleContinue} variant="primary" fullWidth>
              Continue to Submit
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
