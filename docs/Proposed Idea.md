FACULTY OF COMPUTER SCIENCE AND INFORMATION

TECHNOLOGY

UNIVERSITY OF MALAYA

PROJECT PROPOSAL PAPER

YONG YEW SING 23004976 CHOW SHINO

23004896

PROJECT TITLE :

SMART CLASSROOM MANAGEMENT SYSTEM

SUPERVISOR : DR. RAJA JAMILAH RAJA YUSOF


## 1.0 Introduction

Traditional classroom environments often face challenges in managing student attendance, encouraging classroom interaction, and monitoring individual academic performance. Manual attendance-taking can consume valuable teaching time, while limited classroom interaction may make it difficult for lecturers to identify students' understanding and learning difficulties. Furthermore, preparing assessments and monitoring individual student progress can create additional administrative workloads for lecturers.

To address these challenges, this project proposes the development of a Smart Classroom Management System designed to support a classroom of approximately 20 students. The system integrates Internet of Things (IoT) technology with facial recognition, Artificial Intelligence (AI), and interactive learning features to improve classroom administration and enhance the teaching and learning experience (Faritha Banu et al., 2020).

The proposed system will incorporate an IoT-based facial recognition attendance mechanism using a Raspberry Pi connected to a camera installed at the classroom entrance. The camera will capture students' faces, and the facial recognition system will verify their identities before automatically recording their attendance. This approach aims to reduce manual attendance-taking and minimize proxy attendance (Zhao et al., 2022; Ismail et al., 2022).

In addition, the system will provide interactive educational interfaces accessible through mobile devices and computers. Students will be able to participate in classroom activities, submit questions, answer live polls, and complete online quizzes. AI-powered features will also assist lecturers in generating assessment questions from uploaded course materials and analysing students' academic performance.

Furthermore, the system will incorporate learning analytics and personalized learning recommendations by analysing students' attendance, classroom participation, and assessment results. Based on the collected data, the system will identify potential learning difficulties and recommend relevant learning materials to help students improve their understanding.

This initiative supports Sustainable Development Goal 4 (SDG 4): Quality Education by promoting accessible, interactive, and personalized learning experiences through the integration of IoT and AI technologies.


## 2.0 Problem Statement

Traditional classroom management involves several challenges that may affect teaching efficiency and student engagement.

Firstly, manual attendance-taking requires lecturers to spend valuable classroom time checking and recording student attendance. It may also create opportunities for proxy attendance, where students register attendance on behalf of their classmates (Nguyen et al., 2022). Maintaining attendance records manually can also become inconvenient when managing multiple classes and sessions.

Secondly, classroom interaction between lecturers and students may be limited. Some students may hesitate to ask questions or express their difficulties during lessons. Thus, lecturers may find it difficult to identify students who are struggling to understand specific topics (Kocak, 2022).

Thirdly, preparing quizzes and assessments requires considerable time and effort from lecturers. Lecturers need to review course materials, prepare assessment questions, and evaluate students' answers. These tasks may increase their workload, especially when managing multiple classes.

Additionally, lecturers may face difficulties monitoring individual student performance using attendance, participation, and assessment records separately. Students who frequently miss classes, demonstrate declining academic performance, or show limited participation may not be identified early enough.

Lastly, students may struggle to identify their individual knowledge gaps and find suitable learning resources. Providing the same learning materials to all students may not effectively address their different learning needs and academic weaknesses.

Therefore, an integrated Smart Classroom Management System is proposed to address these challenges through IoT-based facial recognition attendance, interactive classroom features, AI-powered assessments, learning analytics, and personalized learning recommendations.


## 3.0 Project Objectives

- i) To analyse the limitations of existing classroom management approaches in terms of attendance management, classroom interaction, assessment preparation, and personalized learning through literature review and requirements elicitation.

- ii) To design and develop a Smart Classroom Management System integrating automated facial recognition attendance, centralized user and attendance management, interactive classroom features, AI-powered quiz generation, learning analytics, and personalized learning recommendations.

iii) To evaluate the functionality and usability of the developed system through structured testing, including functional testing against defined system requirements and User Acceptance Testing (UAT) conducted with student and lecturer end users.


## 4.0 Project Scope

The proposed Smart Classroom Management System will consist of eight main modules. Each module provides specific functionalities while sharing relevant information with other modules to create an integrated classroom management and learning environment.

## 4.1 Module 1: User Management

## Purpose:

To manage student, lecturer, and administrator accounts, including authentication, user profiles, and access permissions.

## Implementation:

The system will provide user registration, login, authentication, and profile management functionalities. Each user will be assigned a specific role, such as student, lecturer, or administrator. Role-Based Access Control (RBAC) will be implemented to ensure that users can only access functions and information according to their assigned permissions.

The system will integrate with the university's Moodle-based learning management system through the Moodle Web Services API. Students and lecturers will sign in with their Moodle credentials using Moodle's token-based authentication, and course and enrolment data will be retrieved from Moodle so that class lists do not need to be maintained separately.

The system will maintain student and lecturer information, including student identification details, course enrolments, and relevant account information. Student facial data required for attendance verification will be securely registered and associated with the corresponding student account. Facial data will only be registered with the student's consent, stored mainly as facial feature representations (embeddings), and accessible only to authorized administrators, in line with the Personal Data Protection Act 2010 (PDPA).

## Expected Outcome:

Provides a centralized and secure user management system that allows students, lecturers, and administrators to access the system according to their respective roles.

## 4.2 Module 2: Dashboard and Notifications

## Purpose:

To provide a centralized overview of important classroom and academic information while keeping users informed about important updates.

## Implementation:


The system will provide role-based dashboards displaying relevant information for students and lecturers.

For students, the dashboard will display attendance status, upcoming deadlines, latest announcements, notifications, and ongoing classroom activities.

For lecturers, the dashboard will provide an overview of class attendance, student participation, assessment activities, and important notifications.

The system will support push notifications and email notifications for important announcements, deadlines, and classroom updates. Students will receive notifications when their attendance has been successfully recorded. Lecturers will also receive alerts when students are identified as potentially at-risk by the Learning Analytics and Early Warning module.

Notifications will be assigned priority levels, such as urgent, important, and general. Urgent and important items, including upcoming deadlines, newly published quizzes, and at-risk alerts, will be highlighted at the top of the dashboard and sent as push notifications, while general updates will appear in the notification feed. This ensures that students do not miss important information.

## Expected Outcome:

Allows students and lecturers to access important information conveniently, reduces missed announcements and deadlines, and provides a centralized communication channel for classroom updates.

## 4.3 Module 3: Attendance Management

## Purpose:

To record, manage, and monitor student attendance across different classes and classroom sessions.

## Implementation:

The system will maintain attendance records for each student based on their registered courses and scheduled classroom sessions.

Attendance records will be automatically received from the Attendance Verification module after successful facial recognition. The system will calculate individual attendance rates, maintain historical attendance records, and allow authorized lecturers to review or manually override attendance records when necessary, such as when a student's face cannot be recognized. Each manual override will be logged for auditing purposes.


Lecturers will also be able to generate attendance reports to monitor student attendance across different sessions and courses.

The system will maintain the attendance status and timestamp for each recorded session. Attendance records will be stored in a centralized database for future reference and learning analytics.

After each session, the finalized attendance records will be synchronized to the corresponding course on Moodle.

## Expected Outcome:

Reduces manual attendance-taking and simplifies attendance monitoring, record management, and administrative tasks for lecturers.

## 4.4 Module 4: Facial Recognition Attendance Verification

## Purpose:

To automatically verify student identity and physical presence in the classroom through an IoT-based facial recognition system.

## Implementation:

The system will utilize an IoT device, such as a Raspberry Pi, connected to a Raspberry Pi Camera Module or a USB webcam installed at the classroom entrance.

When students enter the classroom, the camera will capture their facial images or video frames. To reduce the processing load on the IoT device, the Raspberry Pi will detect faces locally and transmit only the detected face images to the backend server for recognition.

The system will detect and recognize student faces using a facial recognition model. The detected facial features will be compared against registered facial data stored in the system's database to identify the corresponding student. A student will only be marked present after being matched consistently across several consecutive frames, which reduces false matches.

After successful verification, the student's attendance status and timestamp will be automatically submitted to the Attendance Management module.

The system will also provide visual feedback, on a display connected to the Raspberry Pi or on the lecturer's device, to indicate whether a student's identity has been successfully recognized and whether attendance has been recorded. Unrecognized faces or failed recognition attempts will be flagged for further review by lecturers, who can confirm the student's identity or record the attendance manually.

## Expected Outcome:


Automates classroom attendance recording, reduces opportunities for proxy attendance, and minimizes lecturers' administrative workload. The system also aims to provide a convenient and efficient attendance process through IoT-based facial recognition.

## 4.5 Module 5: Classroom Interaction

## Purpose:

To encourage student participation and improve communication between students and lecturers during classroom sessions.

## Implementation:

The system will provide interactive classroom features, including live questions, polls, voting, Q&A sessions, reactions, and an "I Don't Understand" button.

Students will be able to submit questions during lectures, including the option to submit questions anonymously. Lecturers can create live polls, ask questions, and receive student responses in real time.

The system will also allow students to indicate when they are having difficulties understanding a particular topic. These interactions will be recorded to provide lecturers with additional information about classroom engagement and student understanding.

All interactions within this module will be non-graded and intended to support real-time classroom communication. Formal assessments and graded quizzes will be managed separately through the Quiz and Assessment module.

## Expected Outcome:

Encourages active learning, improves communication between students and lecturers, and allows lecturers to identify students' confusion and understanding during classroom sessions.

## 4.6 Module 6: AI-Powered Quiz and Assessment

## Purpose:

To assist lecturers in preparing assessments more efficiently and evaluating students' understanding of course materials.

## Implementation:

The system will allow lecturers to upload course materials, such as lecture notes, PDF documents, and presentation slides.


An AI-powered question generation feature will process the uploaded materials and generate draft assessment questions, including multiple-choice questions and short-answer questions, together with suggested answers.

Lecturers will be able to review, edit, and approve the generated questions before publishing them to students.

Students will access published quizzes through their mobile devices or computers and submit their answers within the allocated time.

Objective questions will be graded automatically by the system, while short-answer responses may be reviewed by lecturers or evaluated using an appropriate AI-assisted assessment approach.

Lecturers will be able to monitor quiz results and identify questions that students frequently answer incorrectly. Assessment results will also be shared with the Learning Analytics and Early Warning module to support student performance monitoring.

The quiz set drafted will sync back to moodle.

## Expected Outcome:

Reduces the time and effort required for quiz preparation while providing lecturers with assessment data that supports performance evaluation, learning analytics, and personalized learning recommendations.

## 4.7 Module 7: Learning Analytics and Early Warning

## Purpose:

To consolidate attendance, classroom participation, and assessment data into meaningful insights, allowing lecturers to monitor student engagement and identify potentially at-risk students at an early stage.

## Implementation:

The system will collect and analyse data from the Attendance Management, Classroom Interaction, and Quiz and Assessment modules.

Several student engagement indicators will be calculated, including:

- Attendance rate and absence frequency.

- Classroom participation frequency.

- Number of questions submitted.

- Frequency of confusion signals.

- Quiz scores and assessment performance trends.


The system will provide lecturer dashboards displaying individual student performance, class-level engagement trends, and assessment performance across different topics and sessions.

A rule-based early warning mechanism will be implemented to identify students who may require additional academic support.

For example, the system may automatically flag students when:

- Their attendance rate falls below the minimum required percentage.

- They are absent for several consecutive sessions.

- Their quiz scores show a continuous decline.

- Their classroom participation decreases significantly.

When a student meets the predefined warning conditions, the system will generate an alert and notify the relevant lecturer through the Dashboard and Notifications module.

Students will also be able to view their own attendance status, engagement summaries, and academic performance indicators.

## Expected Outcome:

Enables lecturers to identify students who may be experiencing academic difficulties at an early stage and take appropriate action before their performance deteriorates further. It also provides students with greater awareness of their own academic progress.

## 4.8 Module 8: Personalized Learning Suggestions

## Purpose:

To provide personalized learning recommendations based on students' quiz results and learning needs, helping them identify knowledge gaps and improve their academic performance.

## Implementation:

The system will allow lecturers to upload course materials, including lecture notes, presentation slides, and other learning resources.

The uploaded materials will be processed and organized into a course-specific knowledge base. This knowledge base will also be shared with the Quiz and Assessment module to support AI-powered question generation.

Based on individual quiz results, the AI system will analyse students' incorrect answers and identify potential knowledge gaps related to specific topics or concepts.


After identifying the knowledge gaps, the system will recommend relevant sections of the lecturer's uploaded learning materials to help students revise the topics they have not fully understood.

In addition, the system will provide supplementary external learning resources, such as relevant educational YouTube videos, recommended search keywords, and other learning materials.

Recommendations will be generated according to individual students' assessment performance rather than providing identical learning suggestions to every student.

For lecturers, the system will summarize the topics and questions that the class most frequently answers incorrectly, and suggest topics that may need to be revisited or reinforced in later lessons, together with the relevant sections of the uploaded materials.

## Expected Outcome:

Helps students identify their weak areas, access relevant learning materials, and improve their understanding through personalized learning recommendations.

## 4.9 Scope Limitations

The following limitations define the boundaries of the proposed system:

- Environmental monitoring and automation (temperature, lighting, CO₂ and air-conditioning control) and desk projection with gesture interaction are excluded, as they require modifications to the building's electrical infrastructure and dedicated hardware for every desk.

- The system is designed and evaluated for a single classroom of approximately 20 students.

- Facial recognition does not include liveness detection. The risk of spoofing with photographs is reduced by placing the camera at the classroom entrance under the lecturer's supervision, and liveness detection is left as future work.

- Push notifications will be supported on Android devices. On iOS devices, notifications will be delivered in-app and by email, as iOS push notifications require a paid Apple Developer Program membership.

- Moodle integration depends on the web service access granted by the university. If access to the university's Moodle is not available, a separate Moodle test instance will be used for development and demonstration.

- AI-powered features depend on a third-party LLM API and require an internet connection.


## 5.0 Proposed System Architecture

The proposed system will adopt a centralized architecture that integrates web and mobile interfaces, IoT hardware, backend services, AI processing components, and a centralized database.

The main components are described below:

## 1. User Interface Layer

Provides user interfaces for students, lecturers, and administrators to access the system functionalities.

Mobile Application: Developed using React Native to support both Android and iOS platforms. It allows students and lecturers to access attendance records, dashboards, quizzes, classroom interactions, notifications, and personalized learning recommendations.

Web Application: Developed using React to provide a web-based interface for administrators, lecturers and students to manage users, courses, attendance records, assessments, and system information.

## 2. IoT Hardware Layer

Consists of a Raspberry Pi connected to a Raspberry Pi Camera Module or USB webcam installed at the classroom entrance. The device captures video frames, detects faces locally, and transmits the detected face images securely to the backend facial recognition service for identification and attendance verification.

## 3. Backend Application Layer

Handles the core business logic and communication between different system modules. Its responsibilities include:

- User authentication and authorization.

- User and course management.

- Attendance processing and record management.

- Classroom interactions.

- Notification management.

- Quiz and assessment management.

- Integration with Moodle for user authentication, enrolment data, and attendance synchronization.

- Communication between the mobile application, web application, AI services, and database.


- Integration with external services, including the LLM API, YouTube Data API, and push and email notification services.

## 4. AI Processing Layer

Provides AI-powered functionalities to enhance classroom management and personalized learning experiences. These functionalities include:

- Facial recognition for automated attendance verification.

- Automatic quiz generation based on learning materials.

- Student performance analysis.

- Personalized learning recommendations based on student performance and learning progress.

## 5. Database Layer

Uses a centralized database to store and manage system information, including:

- User accounts and student profiles.

- Registered facial data or facial feature representations.

- Attendance records.

- Course information and learning materials.

- Classroom interactions.

- Quiz questions and results.

- Student performance records and learning analytics.

The different components will communicate through secure APIs to ensure efficient data exchange and integration. The React Native mobile application and web application will communicate with the backend application layer, while the backend will coordinate requests to the AI processing services and centralized database. During User Acceptance Testing, the backend services and database will be deployed on a cloud server so that participants can access the system from their own mobile devices over the internet.


## 6.0 Proposed Technologies and Tools

The following technologies are proposed for the development of the system. Final technology selection may be adjusted according to implementation requirements.

| Component | Proposed Technology |
| --- | --- |
| Frontend | React Native + Expo (mobile), React + Vite (web) |
| Backend | Python (FastAPI) |
| Database | PostgreSQL with pgvector |
| IoT Hardware | Raspberry Pi |
| Camera | Raspberry Pi Camera Module, Logitech USB webcam |
| Face Detection and Recognition | InsightFace |
| AI analysis and generation | Large Language Model (LLM) via the OpenAI API |
| Notifications | Expo Push Notification Service, email (SMTP) |
| API Communication | REST API |
| Learning Platform Integration | Moodle Web Services API |
| External Learning Resources | YouTube Data API |
| Deployment (UAT) | Cloud server (VPS) |


## 7.0 Project Methodology

The project will adopt an iterative development approach to ensure that each module can be developed, tested, and integrated progressively.

The development process will consist of the following phases:

## Phase 1: Requirement Analysis

Identify system requirements, user roles, module functionalities, hardware requirements, and expected system outcomes.

## Phase 2: System Design

Design the system architecture, database structure, user interfaces, IoT communication flow, and integration between the eight modules.

## Phase 3: System Development

Develop the frontend, backend, database, IoT attendance hardware, facial recognition functionality, Moodle integration, AI-powered assessment features, and other system modules.

## Phase 4: System Integration

Integrate all eight modules to ensure that information can be shared correctly between attendance management, classroom interaction, assessments, learning analytics, and personalized learning suggestions.

## Phase 5: System Testing and Evaluation

Conduct functional testing, integration testing, performance testing, and User Acceptance Testing (UAT) with student and lecturer participants to evaluate system reliability, facial recognition performance, and overall functionality.

## Phase 6: Documentation


Prepare technical documentation, user documentation, testing results, and the final project report.

## 8.0 Expected Project Outcomes

Upon completion, the proposed system is expected to deliver the following outcomes:

- A centralized classroom management platform that supports students, lecturers, and administrators.

- An IoT-based facial recognition attendance system that automatically records student attendance through a classroom camera.

- An interactive classroom environment that encourages student participation and communication.

- An AI-powered quiz generation system that reduces lecturers' assessment preparation workload.

- A learning analytics system that monitors student attendance, engagement, and academic performance.

- An early warning mechanism that helps lecturers identify students who may require additional academic support.

- A personalized learning recommendation system that provides relevant learning resources according to individual students' knowledge gaps.

Overall, the proposed system is expected to improve classroom administration, reduce repetitive academic tasks, encourage student engagement, and support more personalized and data-driven learning experiences.

## 9.0 Project Timeline

The project will be carried out according to the following proposed development schedule.

*FYP 1*

|   |   |   |   |   |   |   | Week |   |   |   |   |   |   |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Task / Week |   |   |   |   |   |   |   |   |   |   |   |   |   |
| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
| Title Selection |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Meeting With |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Supervisor |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Timeline |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Planning |   |   |   |   |   |   |   |   |   |   |   |   |   |


FYP 2


Testing Phase

(incl. UAT)

Report

Modification

Viva 2

Report

Submission

## 10.0 Contribution to Sustainable Development Goal

This project supports Sustainable Development Goal 4 (SDG 4): Quality Education by promoting inclusive, interactive, and technology-supported learning experiences.

The proposed system encourages student participation through interactive classroom features and provides personalized learning recommendations based on individual academic performance. The integration of AI-powered assessments and learning analytics also assists lecturers in

identifying students' learning difficulties and providing appropriate academic support.

Furthermore, the IoT-based attendance system improves classroom administration by automating attendance recording and reducing repetitive manual tasks.

Through the integration of IoT and AI technologies, the project aims to contribute to a more efficient, engaging, and personalized educational environment.

## 11.0 Conclusion

In conclusion, this project proposes the development of a Smart Classroom Management System that integrates eight essential modules to improve classroom administration and enhance the teaching and learning experience.

By incorporating IoT-based facial recognition, the system aims to automate attendance recording and reduce the possibility of proxy attendance. Meanwhile, classroom interaction features will


encourage active student participation, and AI-powered assessments will assist lecturers in preparing quizzes more efficiently.

Furthermore, the integration of Learning Analytics and Early Warning with Personalized Learning Suggestions will provide lecturers with meaningful insights into student performance while helping students identify their individual learning weaknesses.

The integration of these functionalities into a centralized platform is expected to provide a more efficient, interactive, and personalized classroom environment. The proposed system aims to support lecturers in managing classroom activities more effectively while enabling students to take a more active role in their learning process.

## 12.0 References

Faritha Banu, J., Revathi, R., Suganya, M., & Gladiss Merlin, N. R. (2020). IoT based cloud integrated smart classroom for smart and a sustainable campus. Procedia Computer Science, 172, 77–81. https://doi.org/10.1016/j.procs.2020.05.012 [URL 🔗](https://doi.org/10.1016/j.procs.2020.05.012)

Ismail, N. A., Chai, C. W., Samma, H., Salam, M. S., Hasan, L., Wahab, N. H. A., Mohamed, F., Leng, W. Y., & Rohani, M. F. (2022). Web-based university classroom attendance system based on deep learning face recognition. KSII Transactions on Internet and Information Systems, 16(2), 503–523 . http://doi.org/10.3837/tiis.2022.02.008 [URL 🔗](http://doi.org/10.3837/tiis.2022.02.008)

Nguyen, D. D., Le, M. H., Nguyen, X. H., Ngo, H. T., & Nguyen, M. S. (2022). Smart desk in hybrid classroom: Automatic attendance system based on face recognition using MTCNN and ARCFACE. 2022 International Conference on Multimedia Analysis and Pattern Recognition (MAPR), 1–6. https://doi.org/10.1109/MAPR56351.2022.9924775 [URL 🔗](https://doi.org/10.1109/MAPR56351.2022.9924775)

Kocak, O. (2022). A systematic literature review of web-based student response systems: Advantages and challenges. Education and Information Technologies, 27, 2771–2805. https://doi.org/10.1007/s10639-021-10732-8 [URL 🔗](https://doi.org/10.1007/s10639-021-10732-8)

iSAMS. (2026). Cloud-based school management software for K-12 independent schools. https://www.isams.com/platform/school-management-information-system-mis/ [URL 🔗](https://www.isams.com/platform/school-management-information-system-mis/)

Arvia. (2026). Smart classroom solution: Transforming the future of education with interactive technology. https://arvia.my/smart-classroom/ [URL 🔗](https://arvia.my/smart-classroom/)


Zhao, M., Zhao, G., & Qu, M. (2022). College Smart Classroom Attendance Management System Based on Internet of Things. Computational Intelligence and Neuroscience, 2022, 1–9. https://doi.org/10.1155/2022/4953721 [URL 🔗](https://doi.org/10.1155/2022/4953721)

University of Malaya. (2026). UM Spectrum: Student learning portal. https://spectrum.um.edu.my/ [URL 🔗](https://spectrum.um.edu.my/)

Codific. (2026). Attendance Radar: Bluetooth-based student attendance tracking for universities.

[https://attendanceradar.com/](https://attendanceradar.com/)
