import requests
import sys
import time
import json
from datetime import datetime

class TestbookAPITester:
    def __init__(self, base_url="https://4f9d1121-b1a4-4576-997a-e67b9a8aa901.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    print(f"   Response: {response.text[:200]}...")
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health check endpoint"""
        return self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )

    def test_search_api(self, topic="Biology"):
        """Test Google Custom Search API integration"""
        return self.run_test(
            f"Search API for '{topic}'",
            "GET",
            f"api/test-search/{topic}",
            200
        )

    def test_generate_mcq_pdf(self, topic="Heart"):
        """Test MCQ PDF generation endpoint"""
        return self.run_test(
            f"Generate MCQ PDF for '{topic}'",
            "POST",
            "api/generate-mcq-pdf",
            200,
            data={"topic": topic}
        )

    def test_job_status(self, job_id):
        """Test job status tracking"""
        return self.run_test(
            f"Job Status for {job_id}",
            "GET",
            f"api/job-status/{job_id}",
            200
        )

    def test_invalid_job_status(self):
        """Test job status with invalid job ID"""
        return self.run_test(
            "Invalid Job Status",
            "GET",
            "api/job-status/invalid-job-id",
            404
        )

    def test_empty_topic(self):
        """Test empty topic validation"""
        return self.run_test(
            "Empty Topic Validation",
            "POST",
            "api/generate-mcq-pdf",
            400,
            data={"topic": ""}
        )

    def test_download_invalid_file(self):
        """Test download with invalid filename"""
        return self.run_test(
            "Download Invalid File",
            "GET",
            "api/download/nonexistent.pdf",
            404
        )

def main():
    print("🚀 Starting Testbook MCQ Scraper API Tests")
    print("=" * 60)
    
    tester = TestbookAPITester()
    
    # Test 1: Health Check
    success, _ = tester.test_health_check()
    if not success:
        print("❌ Health check failed, API may not be running")
        return 1

    # Test 2: Search API with different topics
    topics_to_test = ["Biology", "Physics", "Heart"]
    for topic in topics_to_test:
        success, response = tester.test_search_api(topic)
        if success and response:
            print(f"   Found {response.get('links_found', 0)} links for '{topic}'")

    # Test 3: Generate MCQ PDF
    success, response = tester.test_generate_mcq_pdf("Heart")
    job_id = None
    if success and response:
        job_id = response.get('job_id')
        print(f"   Job ID: {job_id}")

    # Test 4: Job Status Tracking
    if job_id:
        print(f"\n🔄 Monitoring job progress for 60 seconds...")
        start_time = time.time()
        max_wait_time = 60  # Wait up to 60 seconds
        
        while time.time() - start_time < max_wait_time:
            success, status_response = tester.test_job_status(job_id)
            if success and status_response:
                status = status_response.get('status')
                progress = status_response.get('progress', '')
                print(f"   Status: {status} - {progress}")
                
                if status in ['completed', 'error']:
                    if status == 'completed':
                        pdf_url = status_response.get('pdf_url')
                        mcqs_found = status_response.get('mcqs_found', 0)
                        print(f"   ✅ Job completed! Found {mcqs_found} MCQs")
                        print(f"   PDF URL: {pdf_url}")
                        
                        # Test download endpoint (just check if it exists)
                        if pdf_url:
                            filename = pdf_url.split('/')[-1]
                            download_success, _ = tester.run_test(
                                f"Download PDF {filename}",
                                "GET",
                                f"api/download/{filename}",
                                200
                            )
                    else:
                        print(f"   ❌ Job failed: {progress}")
                    break
            
            time.sleep(3)  # Wait 3 seconds between checks
        else:
            print(f"   ⏰ Job monitoring timed out after {max_wait_time} seconds")

    # Test 5: Error Cases
    tester.test_invalid_job_status()
    tester.test_empty_topic()
    tester.test_download_invalid_file()

    # Test 6: Additional search tests with edge cases
    edge_case_topics = ["XYZ123", ""]
    for topic in edge_case_topics:
        if topic:  # Skip empty string as it's tested separately
            tester.test_search_api(topic)

    # Print final results
    print("\n" + "=" * 60)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())