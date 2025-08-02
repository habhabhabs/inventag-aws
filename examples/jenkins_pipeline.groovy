// Jenkins Pipeline for InvenTag Multi-Account BOM Generation
pipeline {
    agent any
    
    parameters {
        choice(
            name: 'ENVIRONMENT',
            choices: ['production', 'staging', 'development'],
            description: 'Target environment for BOM generation'
        )
        choice(
            name: 'OUTPUT_FORMATS',
            choices: ['excel', 'word', 'json', 'excel,word', 'excel,word,json', 'all'],
            description: 'Output formats to generate'
        )
        string(
            name: 'COMPLIANCE_THRESHOLD',
            defaultValue: '80',
            description: 'Minimum compliance percentage threshold'
        )
        booleanParam(
            name: 'UPLOAD_TO_S3',
            defaultValue: true,
            description: 'Upload generated documents to S3'
        )
        booleanParam(
            name: 'SEND_NOTIFICATIONS',
            defaultValue: true,
            description: 'Send notifications on completion'
        )
        booleanParam(
            name: 'FAIL_ON_SECURITY_ISSUES',
            defaultValue: true,
            description: 'Fail pipeline if security issues are found'
        )
    }
    
    environment {
        // AWS Configuration
        AWS_DEFAULT_REGION = 'us-east-1'
        
        // S3 Configuration
        INVENTAG_S3_BUCKET = credentials('inventag-s3-bucket')
        INVENTAG_S3_KEY_PREFIX = "jenkins-bom-reports/${env.BUILD_NUMBER}"
        
        // Notification Configuration
        INVENTAG_SLACK_WEBHOOK = credentials('slack-webhook-url')
        INVENTAG_TEAMS_WEBHOOK = credentials('teams-webhook-url')
        
        // Prometheus Configuration
        PROMETHEUS_PUSH_GATEWAY_URL = 'http://prometheus-pushgateway:9091'
        PROMETHEUS_JOB_NAME = 'inventag-jenkins'
        PROMETHEUS_INSTANCE_NAME = "${env.NODE_NAME}-${env.BUILD_NUMBER}"
        
        // Python Configuration
        PYTHONPATH = "${env.WORKSPACE}"
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
                
                // Display build information
                script {
                    echo "Starting InvenTag BOM Generation"
                    echo "Environment: ${params.ENVIRONMENT}"
                    echo "Output Formats: ${params.OUTPUT_FORMATS}"
                    echo "Compliance Threshold: ${params.COMPLIANCE_THRESHOLD}%"
                    echo "Upload to S3: ${params.UPLOAD_TO_S3}"
                    echo "Send Notifications: ${params.SEND_NOTIFICATIONS}"
                }
            }
        }
        
        stage('Setup Python Environment') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }
        
        stage('Validate Configuration') {
            steps {
                script {
                    // Select accounts file based on environment
                    def accountsFile = "examples/accounts_${params.ENVIRONMENT}.json"
                    if (!fileExists(accountsFile)) {
                        accountsFile = "examples/accounts_cicd_environment.json"
                    }
                    env.ACCOUNTS_FILE = accountsFile
                }
                
                // Validate configuration with dry run
                sh '''
                    . venv/bin/activate
                    python scripts/cicd_bom_generation.py \
                        --accounts-file ${ACCOUNTS_FILE} \
                        --formats ${OUTPUT_FORMATS} \
                        --compliance-threshold ${COMPLIANCE_THRESHOLD} \
                        --dry-run \
                        --verbose
                '''
            }
        }
        
        stage('Generate BOM') {
            steps {
                withCredentials([
                    [
                        $class: 'AmazonWebServicesCredentialsBinding',
                        credentialsId: 'aws-credentials',
                        accessKeyVariable: 'AWS_ACCESS_KEY_ID',
                        secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                    ]
                ]) {
                    script {
                        // Build command arguments
                        def args = [
                            "--accounts-file ${env.ACCOUNTS_FILE}",
                            "--formats ${params.OUTPUT_FORMATS}",
                            "--compliance-threshold ${params.COMPLIANCE_THRESHOLD}",
                            "--output-dir ./bom_output",
                            "--verbose"
                        ]
                        
                        if (params.UPLOAD_TO_S3) {
                            args.add("--s3-bucket \${INVENTAG_S3_BUCKET}")
                            args.add("--s3-key-prefix \${INVENTAG_S3_KEY_PREFIX}")
                        }
                        
                        if (params.SEND_NOTIFICATIONS) {
                            args.add("--slack-webhook \${INVENTAG_SLACK_WEBHOOK}")
                            args.add("--teams-webhook \${INVENTAG_TEAMS_WEBHOOK}")
                        }
                        
                        if (params.FAIL_ON_SECURITY_ISSUES) {
                            args.add("--fail-on-security-issues")
                        }
                        
                        args.add("--prometheus-gateway \${PROMETHEUS_PUSH_GATEWAY_URL}")
                        args.add("--prometheus-job \${PROMETHEUS_JOB_NAME}")
                        args.add("--prometheus-instance \${PROMETHEUS_INSTANCE_NAME}")
                        
                        // Execute BOM generation
                        sh """
                            . venv/bin/activate
                            python scripts/cicd_bom_generation.py ${args.join(' ')}
                        """
                    }
                }
            }
        }
        
        stage('Process Results') {
            steps {
                script {
                    // Archive generated documents
                    if (fileExists('bom_output')) {
                        archiveArtifacts artifacts: 'bom_output/**/*', fingerprint: true
                    }
                    
                    // Archive CI/CD artifacts
                    def artifacts = [
                        '/tmp/pipeline_summary.json',
                        '/tmp/compliance_gate.json',
                        '/tmp/account_summary.json',
                        '/tmp/s3_links.json',
                        '/tmp/inventag_metrics.prom'
                    ]
                    
                    artifacts.each { artifact ->
                        if (fileExists(artifact)) {
                            archiveArtifacts artifacts: artifact, fingerprint: true
                        }
                    }
                    
                    // Parse results for build status
                    if (fileExists('/tmp/pipeline_summary.json')) {
                        def summary = readJSON file: '/tmp/pipeline_summary.json'
                        
                        // Set build description
                        currentBuild.description = """
                            Environment: ${params.ENVIRONMENT}<br/>
                            Success: ${summary.success ? '✅' : '❌'}<br/>
                            Compliance Gate: ${summary.compliance_gate_passed ? '✅ PASSED' : '❌ FAILED'}<br/>
                            Accounts: ${summary.successful_accounts}/${summary.total_accounts}<br/>
                            Resources: ${summary.total_resources}<br/>
                            Execution Time: ${summary.execution_time_seconds}s
                        """
                        
                        // Fail build if compliance gate failed
                        if (!summary.compliance_gate_passed) {
                            error("Compliance gate failed - build marked as failed")
                        }
                        
                        if (!summary.success) {
                            error("BOM generation failed - build marked as failed")
                        }
                    }
                }
            }
        }
    }
    
    post {
        always {
            // Clean up Python virtual environment
            sh 'rm -rf venv'
            
            // Clean up temporary files
            sh 'rm -f /tmp/pipeline_summary.json /tmp/compliance_gate.json /tmp/account_summary.json /tmp/s3_links.json /tmp/inventag_metrics.prom'
        }
        
        success {
            script {
                if (params.SEND_NOTIFICATIONS) {
                    // Send success notification
                    slackSend(
                        channel: '#devops',
                        color: 'good',
                        message: """
                            ✅ InvenTag BOM Generation Successful
                            Environment: ${params.ENVIRONMENT}
                            Build: ${env.BUILD_URL}
                            Formats: ${params.OUTPUT_FORMATS}
                            Compliance: Passed
                        """
                    )
                }
            }
        }
        
        failure {
            script {
                if (params.SEND_NOTIFICATIONS) {
                    // Send failure notification
                    slackSend(
                        channel: '#devops',
                        color: 'danger',
                        message: """
                            ❌ InvenTag BOM Generation Failed
                            Environment: ${params.ENVIRONMENT}
                            Build: ${env.BUILD_URL}
                            Check logs for details
                        """
                    )
                }
            }
        }
        
        unstable {
            script {
                if (params.SEND_NOTIFICATIONS) {
                    // Send unstable notification
                    slackSend(
                        channel: '#devops',
                        color: 'warning',
                        message: """
                            ⚠️ InvenTag BOM Generation Unstable
                            Environment: ${params.ENVIRONMENT}
                            Build: ${env.BUILD_URL}
                            Some issues detected - check results
                        """
                    )
                }
            }
        }
    }
}