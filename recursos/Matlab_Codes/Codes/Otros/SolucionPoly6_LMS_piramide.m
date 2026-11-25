syms F0 F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 Z0 Z1 Z2 Z3 Z4 Z5 Z6
%%
M = [F12 F11 F10 F9 F8 F7 F6; 
     F11 F10 F9  F8 F7 F6 F5; 
     F10 F9  F8  F7 F6 F5 F4; 
     F9  F8  F7  F6 F5 F4 F3;
     F8  F7  F6  F5 F4 F3 F2;
     F7  F6  F5  F4 F3 F2 F1;
     F6  F5  F4  F3 F2 F1 F0;]; 

 M5 = M(2:end,2:end); M4 = M(3:end,3:end); M3 = M(4:end,4:end);
 M2 = M(5:end,5:end); M1 = M(6:end,6:end);

 det6 = det(M);
 det5 = det(M5);
 det4 = det(M4);
 det3 = det(M3);
 det2 = det(M2);
 det1 = det(M1);
 
 sola = M ; sola(:,1) = [Z6;Z5;Z4;Z3;Z2;Z1;Z0]; sola=det(sola);
 det6 = collect(collect(collect(collect(collect(collect(collect(collect(collect(det6,F4),F5),F3),F2),F1),F9),F8),F7),F10);
 sola = collect(collect(collect(collect(collect(collect(collect(collect(collect(sola,F4),F5),F3),F2),F1),F9),F8),F7),F10);
 
solb = M5; solb(:,1) = [   Z5;Z4;Z3;Z2;Z1;Z0]; solb=det(solb);
det5 = collect(collect(collect(collect(collect(collect(collect(collect(collect(det5,F4),F5),F3),F2),F1),F9),F8),F7),F10);
solb = collect(collect(collect(collect(collect(collect(collect(collect(collect(solb,F4),F5),F3),F2),F1),F9),F8),F7),F10);


solc = M4; solc(:,1) = [      Z4;Z3;Z2;Z1;Z0]; solc=det(solc);
det4 = collect(collect(collect(collect(collect(collect(collect(collect(collect(det4,F4),F5),F3),F2),F1),F9),F8),F7),F10);
solc = collect(collect(collect(collect(collect(collect(collect(collect(collect(solc,F4),F5),F3),F2),F1),F9),F8),F7),F10);


sold = M3; sold(:,1) = [         Z3;Z2;Z1;Z0]; sold=det(sold);
det3 = collect(collect(collect(collect(collect(collect(collect(collect(collect(det3,F4),F5),F3),F2),F1),F9),F8),F7),F10);
sold = collect(collect(collect(collect(collect(collect(collect(collect(collect(sold,F4),F5),F3),F2),F1),F9),F8),F7),F10);


sole = M2; sole(:,1) = [            Z2;Z1;Z0]; sole=det(sole);
det2 = collect(collect(collect(collect(collect(collect(collect(collect(collect(det2,F4),F5),F3),F2),F1),F9),F8),F7),F10);
sole = collect(collect(collect(collect(collect(collect(collect(collect(collect(sole,F4),F5),F3),F2),F1),F9),F8),F7),F10);


solf = M2; solf(:,2) = [             Z2;Z1;Z0]; solf=det(solf);
solg = M2; solg(:,3) = [             Z2;Z1;Z0]; solg=det(solg);
solf = collect(collect(collect(collect(collect(collect(collect(collect(collect(solf,F4),F5),F3),F2),F1),F9),F8),F7),F10);
solg = collect(collect(collect(collect(collect(collect(collect(collect(collect(solg,F4),F5),F3),F2),F1),F9),F8),F7),F10);

 
%%

det6 = ['det6 =' char(det6) ';']; sola = ['a =' char(sola) ';'];
det5 = ['det5 =' char(det5) ';']; solb = ['b =' char(solb) ';'];
det4 = ['det4 =' char(det4) ';']; solc = ['c =' char(solc) ';'];
det3 = ['det3 =' char(det3) ';']; sold = ['d =' char(sold) ';'];
det2 = ['det2 =' char(det2) ';']; sole = ['e =' char(sole) ';'];
                                  solf = ['f =' char(solf) ';'];
                                  solg = ['g =' char(solg) ';'];
text1 =[det6 det5 det4 det3 det2 sola solb solc sold sole solf solg];
 %%

 
text1 = strrep(text1,'*','.*');

for i=1:11
text1 = strrep(text1,['F',num2str(i),'^2'],['F',num2str(i),'.*F',num2str(i),]);
end

for i=2:10
text1 = strrep(text1,['F',num2str(i),'^3'],['F',num2str(i),'.*F',num2str(i),'.*F',num2str(i)]);
end

for i=3:9
text1 = strrep(text1,['F',num2str(i),'^4'],['F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i)]);
end

for i=4:8
text1 = strrep(text1,['F',num2str(i),'^5'],['F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i)]);
end

for i=5:7
text1 = strrep(text1,['F',num2str(i),'^6'],['F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i)]);
end


i=6;
text1 = strrep(text1,'F6^7',['F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i),'.*F',num2str(i)]);

C = strsplit(text1,';');
 